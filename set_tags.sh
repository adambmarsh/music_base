#!/bin/bash

## This script has been verified with `schellcheck`
##
## Make generating xspf playlist easier:
## - Adjust paths on lines 32-35
## - Adjust `source=` on line 107
## - Create a symbolic link to this script file, e.g.;
##   ```
##   sudo ln -s /home/user/scripts/music_base/set_tags.sh /home/user/scripts/set-tags
##   ```

# me="${0##*/}"
# echo "$me called"
# echo
# echo "# received arguments ------->  ${@}     "
# echo "# \$1 ----------------------->  $1       "
# echo "# \$2 ----------------------->  $2       "
# echo "# \$3 ----------------------->  $3       "
# echo "# \$4 ----------------------->  $4       "
# echo "# path to me --------------->  ${0}     "
# echo "# parent path -------------->  ${0%/*}  "
# echo "# my name ------------------>  ${0##*/} "
# echo

## Set paths as appropriate to your system:

activate_path="$HOME/.virtualenvs/music_base/bin/activate"
python_pkg="$HOME/scripts/music_base/tag_setter.py"

# echo "activation path: $activate_path"

Usage() {
    echo "This script sets ID3 tags .flac and .mp3 audio files from a YAML file."
    echo "See example_yml dir in https://github.com/adambmarsh/music_base"
    echo ""
    echo "Usage:"
    echo "    -d \"target directory containing the files to tag \""
    echo "    -y \"input YAML file from which tags are generated and applied to the audio files\""
    echo "    --help"
}

if [[ $# -lt 1 ]]; then
    echo "Insufficient arguments ... "
    echo ""
    Usage
    exit 1
fi


while [[ $# -gt 0 ]];
do
    case "$1" in
        -d|--idir)
            idir="$2"
            shift
            ;;
        -y|--yaml)
            iyaml="$2"
            shift
            ;;
        --help|*)
            Usage
            exit 1
            ;;
    esac
    shift
done

if [[ -d "$idir" ]]; then
    input_dir="$idir"
else
    input_dir=""
fi

if [[ -n "$iyaml" ]] && [[ ! -f $input_dir/$iyaml ]]; then
    echo "error: Bad YAML file"
    Usage
    exit 2
fi

## Use path appropriate to the host system in the directive below:
# shellcheck source=/home/adam/.virtualenvs/generate-vlc-playlist/bin/activate
source "$activate_path" && python "$python_pkg" -d "$input_dir" -y "$iyaml" && deactivate