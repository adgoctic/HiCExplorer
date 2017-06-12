#!/bin/bash

tmp_dir=`mktemp -d`
source activate python2.7
conda install -c bioconda -c conda-forge planemo -y
# planemo_bin='which planemo'
# echo $planemo_bin
# source deactivate
# echo $CONDA_PREFIX
planemo database_create galaxy
curl https://repo.continuum.io/miniconda/Miniconda-latest-Linux-x86_64.sh -o miniconda.sh
chmod +x miniconda.sh
./miniconda.sh -b -p $tmp_dir/conda
# echo $CONDA_PREFIX
planemo conda_init --conda_prefix $tmp_dir/conda
# export PATH=$tmp_dir/conda/bin:$PATH
conda install -y -c bioconda -c conda-forge samtools python=2.7.13 numpy scipy matplotlib=2.0.0 nose flake8 pytables biopython pysam pybigwig intervaltree future six pandas

# source activate hicexplorer_galaxy
# echo $CONDA_PREFIX
pip install .

# echo $CONDA_PREFIX
# Galaxy wrapper testing
planemo test --install_galaxy --galaxy_branch release_17.01 --skip_venv --conda_prefix $tmp_dir/prefix --conda_exec $tmp_dir/conda/bin/conda --conda_dependency_resolution --no_conda_auto_install --no_conda_auto_init --postgres galaxy/wrapper
# planemo test --skip_venv --install_galaxy --no_conda_auto_install --no_conda_auto_init --galaxy_branch release_17.01 --postgres galaxy/wrapper/
# /home/travis/build/maxplanck-ie/HiCExplorer/foo/bin/planemo test --skip_venv --install_galaxy --no_conda_auto_install --no_conda_auto_init --galaxy_branch release_17.01 --postgres galaxy/wrapper/
source deactivate