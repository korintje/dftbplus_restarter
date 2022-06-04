import os, sys, argparse, shutil, hsd

# Global constants
RESTART_DIRNAME = "restart"
COLLECT_DIRNAME = "collect"
ITER_FILENAME = "iter_range.txt"
HSD_FILENAME = "dftb_in.hsd"
XYZ_FILENAME = "geo_end.xyz"
GEN_FILENAME = "geo_end.gen"
CHARGE_FILENAMES = ["charges.bin", "charges.dat"]
OUT_FILENAME = "md.out"
THIS_FILENAME = os.path.basename(__file__)


class Atom():
  """Class of an atom in a MD frame"""
  def __init__(self, element, coord, charge, velocity):
    self.element = element
    self.coord = coord
    self.charge = charge
    self.velocity = velocity


class MDFrame():
  """Class of a MD frame"""
  def __init__(self, iter_num, atom_count, comment, atoms):
    self.iter_num = iter_num
    self.atom_count = atom_count
    self.comment = comment
    self.atoms = atoms
    self.thermostat_state = {}
  
  @classmethod
  def from_xyz_lines(cls, lines, iter_from=0, add_comment=""):
    atom_count = int(lines[0])
    comment = lines[1]
    iter_num = int(comment[comment.find('iter:') + 5:].split()[0]) + iter_from
    comment = f"iter:{iter_num} {add_comment}\n"
    atom_params = [line.split() for line in lines[2:]]
    atoms = []
    for atom_param in atom_params:
      atoms.append(
        Atom(
          atom_param[0],
          [float(v) for v in atom_param[1:4]],
          float(atom_param[4]),
          [float(v) for v in atom_param[5:8]]
        )
      )
    return MDFrame(iter_num, atom_count, comment, atoms)
    
  def load_thermostat(self, filepath):
    """load internal state of the thermostat chain from out file
    x{}: positions, v{}: velocities, and g{}: forces 
    """
    thermostat_state = {}
    with open(filepath, "r") as f:
      while True:
        line = f.readline().strip()
        if not line.startswith("MD step:"):
          continue
        iter_num = int(line[8:].strip().split()[0])
        if iter_num != self.iter_num:
          if not line:
            raise Exception(
              "Specified MD step not found in {}".format(filepath)
            )
          else:
            continue
        while True:
          line = f.readline().strip()
          if line.startswith("x:"):
            xs = f.readline().strip().split()
            thermostat_state["x"] = [float(x) for x in xs]
          elif line.startswith("v:"):
            vs = f.readline().strip().split()
            thermostat_state["v"] = [float(v) for v in vs]
          elif line.startswith("g:"):
            gs = f.readline().strip().split()
            thermostat_state["g"] = [float(g) for g in gs]
          elif line.startswith("MD step:") or not line:
            break
        if len(thermostat_state.keys()) == 3:
          self.thermostat_state = thermostat_state
          break
        else:
          raise Exception(
            "Thermostat parameters not found in the MD step"
          )


class MDTrajectory():
  """Class of collection of MD frames"""
  def __init__(self, frames):
    self.frames = frames
  
  @classmethod
  def from_xyz(cls, filepath, iter_from=0):
    """load MD frames from .xyz file"""
    frames = []
    with open(filepath, "r") as f:
      while True:
        lines = []
        header = f.readline()
        if header.strip() == '':
          break
        try:
          atom_count = int(header)
        except ValueError as e:
          raise ValueError('Expected xyz header but got: {}'.format(e))
        lines.append(atom_count)
        lines.append(f.readline())
        for _i in range(atom_count):
          lines.append(f.readline())
        frames.append(
          MDFrame.from_xyz_lines(lines, iter_from=iter_from)
        )
    return MDTrajectory(frames)
      
  def load_geometry(self, gen_filepath):
    """load periodicity information from gen file"""
    with open(gen_filepath, "r") as f:
      lines = f.read().splitlines()
      self.geometry_type = lines[0].split()[1]
      self.is_periodic = True if self.geometry_type in ["S", "F"] else False
      if self.is_periodic:
        self.lattice_vectors = [
          [float(v) for v in line.split()] for line in lines[-3:]
        ]
      else:
        self.lattice_vectors = [[], [], []]

  def get_index_from_iter(self, iter_num):
    """Get MD frame index from the iter number"""
    for i, frame in enumerate(self.frames):
      if frame.iter_num == iter_num:
        return i
    print("The specified MD iter number is not found.")
    return -1

  def get_all_elements(self):
    """Return list of used elements in the trajectory"""
    elements = []
    for atom in self.frames[0].atoms:
      element = atom.element
      if not element in elements:
        elements.append(element)
    return elements


class IterRange():

  def __init__(self, iter_from, iter_until):
    self._from = iter_from
    self._until = iter_until

  @classmethod
  def load_file(cls, filename):
    """Load iteration range from ITER_FILENAME"""
    try:
      with open(filename, "r") as f:
        first = f.readline().strip()
        iter_from =  int(first) if first else 0
        second = f.readline().strip()
        iter_until =  int(second) if second else 0
        iter_range = IterRange(iter_from, iter_until)
    except:
      iter_range = IterRange(0, 0)
    return iter_range
  
  def update(self, traj):
    """Update iteration range by reading frames"""
    self._until = self._from + traj.frames[-1].iter_num

  def save(self, filename):
    """Save iteration range into file"""
    with open(filename, "w") as f:
      f.write(str(self._from) + "\n")
      f.write(str(self._until))


# Main function
def make_files(
  max_iter=0, extra_files=[], output_dir=None, self_copy=False,
  write_over=False, force_restart=False, restart_from=-1,
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
  traj = MDTrajectory.from_xyz(XYZ_FILENAME)
  traj.load_geometry(GEN_FILENAME)

  # Load and update latest iteration number in the current run
  iter_range = IterRange.load_file(ITER_FILENAME)
  iter_range.update(traj)
  iter_range.save(ITER_FILENAME)

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
  if (max_iter != 0) and (iter_range._until >= max_iter):
    print(f"MD simulation has reached max iteration number: {max_iter}")
    sys.exit(0)

  # Stop the script if no iter increase in the current run
  if (iter_range._from >= iter_range._until) and (force_restart is False):
    print("No iteration increase in the current run.")
    sys.exit(0)

  # Create restart directory under the current directory if not exists and copy files
  if not write_over:
    os.makedirs(restart_dirname, exist_ok=True)
    for filename in extra_files + CHARGE_FILENAMES:
      if os.path.exists(filename):
        shutil.copy(filename, os.path.join(restart_dirname, filename))
    if self_copy:
      shutil.copy(THIS_FILENAME, os.path.join(restart_dirname, THIS_FILENAME))

  # Load hsd input file
  hsdinput = hsd.load(HSD_FILENAME)
  hsdinput["Geometry"].pop("GenFormat", None)

  # Set element type names
  elements = traj.get_all_elements()
  hsdinput["Geometry"]["TypeNames"] = elements

  # Set periodicity and cell information
  hsdinput["Geometry"]["Periodic"] = traj.is_periodic
  if traj.is_periodic:
    hsdinput["Geometry"]["LatticeVectors"] = traj.lattice_vectors
    hsdinput["Geometry"]["LatticeVectors.attrib"] = "Angstrom"
  
  # Get fram from the specified index
  if restart_from == -1:
    frame_index = -1
  else:
    frame_index = traj.get_index_from_iter(restart_from)
  frame = traj.frames[frame_index]

  # Set atom ids and coords
  atom_descriptions = []
  for atom in frame.atoms:
    element_id = elements.index(atom.element) + 1
    atom_descriptions.append([str(element_id)] + atom.coord)
  hsdinput["Geometry"]["TypesAndCoordinates"] = atom_descriptions
  hsdinput["Geometry"]["TypesAndCoordinates.attrib"] = "Angstrom"

  # Set initial charges when restarting from the last MD iteration
  charges_file_exists = False
  for filename in CHARGE_FILENAMES:
    if os.path.exists(os.path.join(restart_dirname, filename)):
      charges_file_exists = True 
  if restart_from == -1 and charges_file_exists:
    hsdinput["Hamiltonian"]["DFTB"]["ReadInitialCharges"] = True
  else:
    hsdinput["Hamiltonian"]["DFTB"]["ReadInitialCharges"] = False

  # Set velocities of atoms
  velocities = [atom.velocity for atom in frame.atoms]
  if "VelocityVerlet" in hsdinput["Driver"]:
    hsdinput["Driver"]["VelocityVerlet"]["Velocities"] = velocities
    hsdinput["Driver"]["VelocityVerlet"]["Velocities.attrib"] = "AA/ps"
  
    # Set thermostat settings
    if "Thermostat" in hsdinput["Driver"]["VelocityVerlet"]:
      if "NoseHoover" in hsdinput["Driver"]["VelocityVerlet"]["Thermostat"]:
        frame.load_thermostat(OUT_FILENAME)
        hsdinput["Driver"]["VelocityVerlet"]["Thermostat"]["NoseHoover"]["Restart"] = frame.thermostat_state
      elif "None" in hsdinput["Driver"]["VelocityVerlet"]["Thermostat"]:
        hsdinput["Driver"]["VelocityVerlet"]["Thermostat"]["None"].pop("InitialTemperature", None)

  # Update hsd input file
  hsd.dump(hsdinput, os.path.join(restart_dirname, HSD_FILENAME))

  # Write updated iter range file
  with open(os.path.join(restart_dirname, ITER_FILENAME), "w") as f:
    f.write(str(iter_range._from + frame.iter_num))


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
