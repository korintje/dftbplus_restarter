import os, argparse, itertools, shutil

GEN_FILENAME = "geo_end.gen"
ITER_FILENAME = "iter_range.txt"
XYZ_FILENAME = "geo_end.xyz"
RESTART_DIRNAME = "restart"
COLLECT_DIRNAME = "collect"
CURRENT_PATH = os.getcwd()


# Load iteration range from ITER_FILENAME
def load_iter_range(filename):
  try:
    with open(filename, "r") as f:
      first = f.readline().strip()
      iter_from =  int(first) if first else None
      second = f.readline().strip()
      iter_until =  int(second) if second else None
      iter_range = {"from": iter_from, "until": iter_until}
  except:
    iter_range = {"from": None, "until": None}
  return iter_range


# Read frame file to give frame list which have modified xyz lines
def load_frames(frame_filename, iter_from=0, add_comment=""):
  frames = []
  with open(frame_filename, "r") as f:
    while True:
      lines = []
      header = f.readline()
      if header.strip() == '':
        break
      try:
        natoms = int(header)
      except ValueError as e:
        raise ValueError('Expected xyz header but got: {}'.format(e))
      lines.append(header)
      comment = f.readline()
      iter_number = int(comment[comment.find('iter:') + 5:].split()[0]) + iter_from
      lines.append(f"iter:{iter_number} {add_comment}\n")
      for i in range(natoms):
        lines.append(f.readline())
      frames.append(lines)
  return frames


# Get MD iteration number from given xyz frame index
def get_iter_from_frame(frame):
  comment = frame[1]
  iter_number = int(comment[comment.find('iter:') + 5:].split()[0])
  return iter_number


# Get frame backward index from MD iteration number
def get_backindex_from_iter(frames, iter_number):
  for bi, frame in enumerate(frames[::-1]):
    if get_iter_from_frame(frame) == iter_number:
      return bi
  return None


# Main function
def collect(
  extra_files=[], output_dirname=COLLECT_DIRNAME, input_dirname=RESTART_DIRNAME,
  properties=False, lattice=False, add_mode=False, disjoint=False
):
  # Prepare additional comment line
  params = []
  if properties:
    params.append("Properties=species:S:1:pos:R:3:charge:R:1:vel:R:3")
  if lattice:
    with open(GEN_FILENAME) as f:
      vec_lines = f.read().splitlines()[-3:]
    vec_lines_fmt = []
    for vec_line in vec_lines:
      vec = [float(v) for v in vec_line.split()]
      if len(vec) == 3:
        vec_line_fmt = [str(v) for v in vec]
        vec_lines_fmt.append(" ".join(vec_line_fmt))
      else:
        vec_lines_fmt = []
        break
    lline = " ".join(vec_lines_fmt)
    params.append(f'Lattice="{lline}"')
  comment = " ".join(params)

  # Create collection directory under the current directory if not exists
  os.makedirs(output_dirname, exist_ok=True)
  collected_xyz = os.path.join(output_dirname, XYZ_FILENAME)

  # Recursively append restart MD results
  current_iter = 0
  collected_frames = []

  # Read exsiting collected frames if add-mode is True
  if add_mode and os.path.isfile(collected_xyz):
    frames = load_frames(collected_xyz)
    collected_frames += frames
    current_iter = get_iter_from_frame(frames[-1])

  while True:

    # If no XYZ_FILENAME in the current directory, break loop
    if not os.path.exists(XYZ_FILENAME):
      break
    
    # Append frames of the current run
    iter_from = load_iter_range(ITER_FILENAME)["from"]
    if (iter_from is None) or (disjoint):
      iter_from = current_iter
    frames = load_frames(XYZ_FILENAME, iter_from=iter_from, add_comment=comment)
    backward_index = get_backindex_from_iter(collected_frames, iter_from)
    if backward_index:
      collected_frames = collected_frames[:-backward_index] + frames
    else:
      collected_frames += frames
    current_iter = get_iter_from_frame(frames[-1])

    # Move to the child directory or break loop
    if not os.path.isdir(input_dirname):
      break
    if os.path.samefile(CURRENT_PATH, os.path.join(CURRENT_PATH, input_dirname)):
      break
    os.chdir(input_dirname)
      
  
  # Save collected frames in COLLECT_DIRNAME
  os.chdir(CURRENT_PATH)
  with open(collected_xyz, "w") as f:
    f.writelines(list(itertools.chain.from_iterable(collected_frames)))
  for filename in extra_files:
    shutil.copy(filename, os.path.join(output_dirname, filename))


if __name__ == "__main__":

  # Parse given arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--extra-files", "-e",
    default=[],
    help="Specified files will be additionally copied to the collect directory.", 
    nargs="*"
  )
  parser.add_argument(
    "--output-dir", "-o",
    type=str,
    default=COLLECT_DIRNAME,
    help="Directory name of the directory in which result file will be saved. Default: 'collect'."
  )
  parser.add_argument(
    "--input-dir", "-i",
    type=str,
    default=RESTART_DIRNAME,
    help="Directory name of the recursive restart run. Default: 'restart'. If set as '.', does not collect recursively."
  )
  parser.add_argument(
    "--properties", "-p",
    action="store_true",
    help="Properties line will be added according to the extxyz format."
  )
  parser.add_argument(
    "--lattice", "-l",
    action="store_true",
    help="Lattice condition will be added according to the extxyz format."
  )
  parser.add_argument(
    "--add-mode", "-a",
    action="store_true",
    help="Frames will be added under the existing frames in the collection file. \
          If their iter ranges are not consecutive, you should also specify -i."
  )
  parser.add_argument(
    "--disjoint", "-d",
    action="store_true",
    help="All iter range files will be ignored and simply join frames."
  )
  args = parser.parse_args()

  # Run main function
  collect(
    extra_files=args.extra_files,
    output_dirname=args.output_dir,
    input_dirname=args.input_dir,
    properties=args.properties,
    lattice=args.lattice,
    add_mode=args.add_mode,
    disjoint=args.disjoint
  )