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
def load_gen(filename):
  with open(filename, "r") as f:
    atom = f.read().splitlines()
  return [line.split() for line in atom]


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
    "--extra-files", "-e",
    default=[],
    help="Specified files will be additionally copied to the restart directory.", 
    nargs="*"
  )
  parser.add_argument(
    "--dirname", "-d",
    type=str,
    help="Directory name to be created to store input files for restart run. Default: 'restart'."
  )
  parser.add_argument(
    "--recursive", "-r",
    action="store_true",
    help="This script itself will be copied to the restart directory.", 
  )
  parser.add_argument(
    "--overwrite", "-o", 
    action="store_true",
    help="Input files are overwritten and output frames are collected to another directory."
  )
  parser.add_argument(
    "--force-restart", "-f",
    action="store_true",
    help="Create restart files even if no iter increase in the current run."
  )
  args = parser.parse_args()
  dirname = args.dirname
  if args.overwrite:
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

  # Append frames to the file in collect directory if overwrite mode
  if args.overwrite:
    import restart_collector
    restart_collector.collect(
      extra_files=args.extra_files,
      restart_dirname=restart_dirname,
      collect_dirname=collect_dirname, 
      add_mode=True,
    )

  # Stop the script if reached maximum iteration number
  iter_max = args.max_iter
  if (iter_max != 0) and (iter_until >= iter_max):
    print(f"MD simulation has reached max iteration number: {iter_max}")
    sys.exit(0)

  # Stop the script if no iter increase in the current run
  if (iter_from >= iter_until) and (args.force_restart is False):
    print("No iteration increase in the current run.")
    sys.exit(0)

  # Create restart directory under the current directory if not exists and copy files
  if not args.overwrite:
    os.makedirs(restart_dirname, exist_ok=True) 
    for filename in args.extra_files + [CHARGE_FILENAME]:
      shutil.copy(filename, os.path.join(restart_dirname, filename))
    if args.recursive:
      shutil.copy(THIS_FILENAME, os.path.join(restart_dirname, THIS_FILENAME))
  
  # Load gen of end frame
  end_gen = load_gen(GEN_FILENAME)

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
  hsd.dump(hsdinput, os.path.join(restart_dirname, HSD_FILENAME))

  # Write updated iter range file
  save_iter_range(os.path.join(restart_dirname, ITER_FILENAME), iter_from=iter_until)
