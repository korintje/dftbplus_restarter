import os, sys, json, argparse, shutil
import hsd

# Global constants
DIRNAME = "restart"
ITER_FILENAME = "iter_range.json"
HSD_FILENAME = "dftb_in.hsd"
XYZ_FILENAME = "geo_end.xyz"
GEN_FILENAME = "geo_end.gen"
CHARGE_FILENAME = "charges.bin"
THIS_FILENAME = os.path.basename(__file__)


# Save iteration range into file: ITER_FILENAME
def save_iter_range(filename, iter_from, iter_until):
  with open(filename, "w") as f:
    json.dump({"from": iter_from, "until": iter_until}, f)


# Load iteration range from file: ITER_FILENAME
def load_iter_range(filename):
  try:
    with open(filename, "r") as f:
      iter_range = json.load(f)
  except:
    iter_range = {"from": 0, "until": 0}
  return iter_range


# Get gen file lines
def read_gen(filename):
  with open(filename, "r") as f:
    atom = f.read().splitlines()
  return [line.split() for line in atom]


# Read xyz file to give frame list which have modified xyz lines
def get_frames_from():
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
      f.readline()
      for i in range(natoms):
        lines.append(f.readline())
      frames.append(lines)
  return frames


# Main process
if __name__ == "__main__":

  # Parse given arguments
  parser = argparse.ArgumentParser()
  parser.add_argument(
    "--max-iter", "-m",
    type=int,
    default=0,
    help="The scripts does not produce any files if MD iteration has reached this value. 0 means infinite."
  )
  parser.add_argument(
    "--add-files", "-a",
    default=[],
    help="Specified files will be additionally copied to the restart directory.", 
    nargs="*"
  )
  parser.add_argument(
    "--dirname", "-d",
    type=str,
    default=DIRNAME,
    help="Directory name to be created to store input files for restart run. Default: 'restart'."
  )
  parser.add_argument(
    "--recursive", "-r",
    action="store_true",
    help="If specified, this script itself will be copied to the restart directory.", 
  )
  parser.add_argument(
    "--overwrite", "-o", 
    action="store_true",
    help="If specified, exisiting input files will be overwritten instead of creating new directory."
  )
  parser.add_argument(
    "--force-restart", "-f",
    action="store_true",
    help="If specified, create restart files even if no iter increase in the current run."
  )
  args = parser.parse_args()
  if args.overwrite:
    dirname = "."
  else:
    dirname = args.dirname

  # Get iteration range in the current run
  iter_range = load_iter_range(ITER_FILENAME)
  iter_from = iter_range["from"]
  frames = get_frames_from()
  iter_until = iter_from + len(frames) - 1
  save_iter_range(ITER_FILENAME, iter_from, iter_until)

  # Stop the script if reached maximum iteration number
  iter_max = args.max_iter
  if (iter_max != 0) and (iter_until >= iter_max):
    print(f"MD simulation has reached max iteration number: {iter_max}")
    sys.exit(0)

  # Stop the script if no iter increase in the current run
  if (iter_from >= iter_until) and (args.force_restart is False):
    print(f"No iteration increase in the current run.")
    sys.exit(0)

  # Create restart directory under the current directory if not exists and copy files
  if args.overwrite is False:
    os.makedirs(dirname, exist_ok=True) 
    for filename in args.add_files + [CHARGE_FILENAME]:
      shutil.copy(filename, os.path.join(dirname, filename))
    if args.recursive:
      shutil.copy(THIS_FILENAME, os.path.join(dirname, THIS_FILENAME))
  
  # Load gen of end frame
  end_gen = read_gen(GEN_FILENAME)

  # Get velocities of the end frame
  end_frame = [line.split() for line in frames[-1]]
  end_velocities = [vec[5:8] for vec in end_frame[2:]]

  # Update and write hsd input file
  hsdinput = hsd.load(HSD_FILENAME)
  hsdinput["Geometry"]["GenFormat"] = end_gen
  for k in hsdinput["Hamiltonian"].keys():
    if k == "DFTB":
      hsdinput["Hamiltonian"][k]["ReadInitialCharges"] = True
  for k in hsdinput["Driver"].keys():
    if k == "VelocityVerlet":
      hsdinput["Driver"][k]["Velocities"] = end_velocities
      hsdinput["Driver"][k]["Velocities.attrib"] = "AA/ps"
  hsd.dump(hsdinput, os.path.join(dirname, HSD_FILENAME))

  # Write updated iter range file 
  save_iter_range(os.path.join(dirname, ITER_FILENAME), iter_until, None)
