import os, sys, argparse, shutil, hsd

# Global constants
RESTART_DIRNAME = "restart"
COLLECT_DIRNAME = "collect"
ITER_FILENAME = "iter_range.txt"
HSD_FILENAME = "dftb_in.hsd"
XYZ_FILENAME = "geo_end.xyz"
GEN_FILENAME = "geo_end.gen"
CHARGE_FILENAME = "charges.bin"
THIS_FILENAME = os.path.basename(__file__)


# Save iteration range into file: ITER_FILENAME
def save_iter_range(filename, iter_from="", iter_until=""):
  with open(filename, "w") as f:
    f.write(str(iter_from) + "\n")
    f.write(str(iter_until))


# Load iteration range from ITER_FILENAME
def load_iter_range(filename):
  try:
    with open(filename, "r") as f:
      first = f.readline().strip()
      iter_from =  int(first) if first else 0
      second = f.readline().strip()
      iter_until =  int(second) if second else 0
      iter_range = {"from": iter_from, "until": iter_until}
  except:
    iter_range = {"from": 0, "until": 0}
  return iter_range


# Get gen file lines
def load_gen():
  with open(GEN_FILENAME, "r") as f:
    lines = f.read().splitlines()
  return [line.split() for line in lines]


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


# Get hashmap; key = element, value = index number of gen
def get_element_indexes():
  atom = load_gen()
  elements = atom[1]
  element_indexes = {element: index + 1 for index, element in enumerate(elements)}
  return element_indexes


# Get element lists from gen
def get_elements():
  atom = load_gen()
  elements = atom[1]
  return elements


# get periodicity from gen file
def get_geometry_type():
  atom = load_gen()
  geometry_type = atom[0][1]
  return geometry_type


# Get MD iteration number from given xyz frame index
def get_iter_from_frame(frame):
  comment = frame[1]
  iter_number = int(comment[comment.find('iter:') + 5:].split()[0])
  return iter_number


# Get frame index from MD iteration number
def get_index_from_iter(frames, iter_number):
  for i, frame in enumerate(frames):
    if get_iter_from_frame(frame) == iter_number:
      return i
  print("The MD iter number you specified is not found. \
    The last iter number is used instead.")
  return -1


# Read maximum iteration number from .hsd file
def get_max_iter_from_hsd():
  hsdinput = hsd.load(HSD_FILENAME)
  steps = hsdinput["Driver"]["VelocityVerlet"]["Steps"]
  max_iter = int(steps) if steps else 0
  return max_iter


# Main function
def make_files(
  max_iter=0, extra_files=[], output_dir=None, self_copy=False,
  write_over=False, force_restart=False, restart_from=0,
):

# Set output directory name
  dirname = output_dir
  if write_over:
    restart_dirname = "."
    collect_dirname = dirname if dirname else COLLECT_DIRNAME
  else:
    restart_dirname = dirname if dirname else RESTART_DIRNAME
    collect_dirname = COLLECT_DIRNAME
  
  # Get frames from xyz file
  frames = load_frames(XYZ_FILENAME)

  # Load and update latest iteration number in the current run
  iter_from = load_iter_range(ITER_FILENAME)["from"]
  iter_until = iter_from + get_iter_from_frame(frames[-1])
  save_iter_range(ITER_FILENAME, iter_from=iter_from, iter_until=iter_until)

  # Append frames to the file in collect directory if write_over mode
  if write_over:
    import restart_collector
    restart_collector.collect(
      extra_files=extra_files,
      input_dirname=restart_dirname,
      output_dirname=collect_dirname, 
      add_mode=True,
    )

  # Stop the script if reached maximum iteration number
  if (max_iter != 0) and (iter_until >= max_iter):
    print(f"MD simulation has reached max iteration number: {max_iter}")
    sys.exit(0)

  # Stop the script if no iter increase in the current run
  if (iter_from >= iter_until) and (force_restart is False):
    print("No iteration increase in the current run.")
    sys.exit(0)

  # Create restart directory under the current directory if not exists and copy files
  if not write_over:
    os.makedirs(restart_dirname, exist_ok=True) 
    for filename in extra_files + [CHARGE_FILENAME]:
      shutil.copy(filename, os.path.join(restart_dirname, filename))
    if self_copy:
      shutil.copy(THIS_FILENAME, os.path.join(restart_dirname, THIS_FILENAME))

  # Load hsd input file
  hsdinput = hsd.load(HSD_FILENAME)
  hsdinput["Geometry"].pop("GenFormat", None)

  # Set element type names
  hsdinput["Geometry"]["TypeNames"] = get_elements()

  # Set periodicity and cell information  
  is_periodic = True if get_geometry_type() in ["S", "F"] else False
  hsdinput["Geometry"]["Periodic"] = is_periodic
  if is_periodic:
    lattice_vectors = []
    for cell_line in load_gen()[-3:]:
      vec = [float(v) for v in cell_line]
      lattice_vectors.append(vec)
    hsdinput["Geometry"]["LatticeVectors"] = lattice_vectors
    hsdinput["Geometry"]["LatticeVectors.attrib"] = "Angstrom"
  
  # Set types and coordinates of atoms
  if restart_from == -1:
    frame_index = -1
  else:
    frame_index = get_index_from_iter(frames, restart_from)
  str_frame = frames[frame_index]
  frame = [line.split() for line in str_frame]
  element_names = [vec[0] for vec in frame[2:]]
  indexes = [get_element_indexes()[element] for element in element_names]
  xyzs = [vec[1:4] for vec in frame[2:]]
  element_xyzs = []
  for (index, xyz) in zip(indexes, xyzs):
    xyz = [float(string) for string in xyz]
    atom = [index] + xyz
    element_xyzs.append(atom)
  hsdinput["Geometry"]["TypesAndCoordinates"] = element_xyzs

  # Set an initial charge setting
  for k in hsdinput["Hamiltonian"].keys():
    if k == "DFTB":
      hsdinput["Hamiltonian"][k]["ReadInitialCharges"] = True

  # Set velocities of atoms
  velocities = [vec[5:8] for vec in frame[2:]]
  for k in hsdinput["Driver"].keys():
    if k == "VelocityVerlet":
      hsdinput["Driver"][k]["Velocities"] = velocities
      hsdinput["Driver"][k]["Velocities.attrib"] = "AA/ps"

  # Update hsd input file
  hsd.dump(hsdinput, os.path.join(restart_dirname, HSD_FILENAME))

  # Write updated iter range file
  save_iter_range(
    os.path.join(restart_dirname, ITER_FILENAME),
    iter_from = iter_from + get_iter_from_frame(str_frame)
  )


# Main process
if __name__ == "__main__":

  # Parse given arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--max-iter", "-m",
    default=0,
    type=int,
    help="The scripts does not produce any files if MD iteration has reached this value. 0 means infinite."
  )
  parser.add_argument(
    "--extra-files", "-e",
    default=[],
    help="Specified files will be additionally copied to the restart directory.", 
    nargs="*"
  )
  parser.add_argument(
    "--output-dir", "-o",
    type=str,
    help="Directory name to be created to store input files for restart run."
  )
  parser.add_argument(
    "--self-copy", "-s",
    action="store_true",
    help="This script itself will be copied to the restart directory.", 
  )
  parser.add_argument(
    "--write-over", "-w", 
    action="store_true",
    help="Input files are overwritten and output frames are collected to the directory specified in -o option."
  )
  parser.add_argument(
    "--restart-from", "-f",
    default=-1,
    type=int,
    help="Restart from the specified MD iter number. -1 means the last iter number."
  )
  args = parser.parse_args()
  
  make_files(
    max_iter=args.max_iter,
    extra_files=args.extra_files,
    output_dir=args.output_dir,
    self_copy=args.self_copy,
    write_over=args.write_over,
    force_restart=False,
    restart_from=args.restart_from,
  )
