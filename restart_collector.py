import os, json, argparse, itertools, shutil

XYZ_FILENAME = "geo_end.xyz"
GEN_FILENAME = "geo_end.gen"
ITER_FILENAME = "iter_range.json"
RESTART_DIRNAME = "restart"
COLLECT_DIRNAME = "collect"
CURRENT_PATH = os.getcwd()


# Load iteration range from file: ITER_FILENAME
def load_iter_range(filename):
  try:
    with open(filename, "r") as f:
      iter_range = json.load(f)
  except:
    iter_range = {"from": 0, "until": 0}
  return iter_range


# Read xyz file to give frame list which have modified xyz lines
def get_frames_from(iter_from, add_comment=""):
  frames = []
  with open(XYZ_FILENAME, "r") as f:
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


# Main process
if __name__ == "__main__":

  # Parse given arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--add-files", "-a",
    default=[],
    help="Specified files will be additionally copied to the collect directory.", 
    nargs="*"
  )
  parser.add_argument(
    "--collect-dirname", "-c",
    type=str,
    default=COLLECT_DIRNAME,
    help="Directory name of the directory in which result file will be saved. Default: 'collect'."
  )
  parser.add_argument(
    "--restart-dirname", "-r",
    type=str,
    default=RESTART_DIRNAME,
    help="Directory name of the recursive restart run. Default: 'restart'."
  )
  parser.add_argument(
    "--properties", "-p",
    action="store_true",
    help="If specified, properties line will be added according to the extxyz format."
  )
  parser.add_argument(
    "--lattice", "-l",
    action="store_true",
    help="If specified, lattice condition will be added according to the extxyz format."
  )
  args = parser.parse_args()

  # Prepare additional comment line
  params = []
  if args.properties:
    params.append("Properties=species:S:1:pos:R:3:charge:R:1:vel:R:3")
  if args.lattice:
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

  # Create collect directory under the current directory if not exists
  os.makedirs(args.collect_dirname, exist_ok=True)

  # Recursively append restart MD results
  collected_frames = []
  while True:
    
    # If no .xyz file in the current directory, break loop
    if not os.path.exists(XYZ_FILENAME):
      break
    
    # Append frames of the current run
    iter_range = load_iter_range(ITER_FILENAME)
    iter_from = iter_range["from"]
    iter_until = iter_range["until"]
    frames = get_frames_from(iter_from, add_comment=comment)
    collected_frames += frames
    
    # If no restart directory in the current directory, break loop
    if os.path.isdir(args.restart_dirname) is False:
      break
    
    # Move to the child directory
    os.chdir(args.restart_dirname)
    
    # Remove frames which have later number than start iteration number of the next MD run
    next_iter_range = load_iter_range(ITER_FILENAME)
    next_iter_from = next_iter_range["from"]
    next_iter_until = next_iter_range["until"]
    if next_iter_until:
      delete_iter_count = iter_until - next_iter_from + 1
      collected_frames = collected_frames[:-delete_iter_count]
  
  # Save collected frames in COLLECT_DIRNAME
  os.chdir(CURRENT_PATH)
  with open(os.path.join(args.collect_dirname, XYZ_FILENAME), "w") as f:
    f.writelines(list(itertools.chain.from_iterable(collected_frames)))
  for filename in args.add_files:
    shutil.copy(filename, os.path.join(args.collect_dirname, filename))
  