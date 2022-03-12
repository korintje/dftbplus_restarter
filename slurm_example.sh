#!/bin/sh
#SBATCH -p i8cpu
#SBATCH -N 2
#SBATCH -n 256
#SBATCH --signal=B:USR1@120

module unload intel_mpi
module load openmpi/4.0.4-intel-2020.2.254
module load intel_mpi/2020.2.254

this_fname="slurm_example.sh"
max_steps=30000

resubmitter()
{
  echo "Caught timeout signal"  
  python restart_filemaker.py -m ${max_steps} -e ${this_fname} -r
  if [ -d restart ]; then
    cd restart
    sbatch ${this_fname}
    echo "Resubmit MD job"
  else
    echo "Resubmit loop has finished"
  fi
  exit 0
}

trap resubmitter USR1
srun dftb+ > ./log.log &
wait