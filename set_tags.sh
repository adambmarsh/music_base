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

activate_path="$HOME/scripts/music_base/.venv/bin/activate"
python_pkg_dir="$HOME/scripts/music_base"
python_pkg="$python_pkg_dir/tag_setter.py"

# echo "activation path: $activate_path"

Usage() {
    echo "This program sets ID3 tags .flac and .mp3 audio files from a YAML file."
    echo "Make sure the audio files have names composed of track numbers and titles as in the YAML file." 
    echo "See example_yml dir in https://github.com/adambmarsh/music_base"
    echo ""
    echo "Usage:"
    echo "    -d target directory containing the files to tag" 
    echo "    -y name of the input YAML file from which to generate tags and apply them to the audio files; "
    echo "       if the input file name is absent, it is assumed to share the name and location of the target "
    echo "       directory."
    echo "    --help"
}

# if [[ $# -lt 1 ]]; then
#     echo "Insufficient arguments ... "
#     echo ""
#     Usage
#     exit 1
# fi


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
    input_dir=$(pwd)
fi

if [[ -n "$iyaml" ]] && [[ ! -f $input_dir/$iyaml ]]; then
    echo "error: Bad YAML file"
    Usage
    exit 2
fi

cur_dir=$(pwd)

set_mp3_date() {
    count=$(find "$input_dir" -iname '*.mp3' 2>/dev/null | wc -l)

    if [ "$count" != 0 ]; then
        echo "Setting mp3 date field ..."
        year=$(ffprobe "$input_dir"/01_* 2>&1 | sed -E -n 's/^ *TDOR *: (.*)/\1/p')

        for i in "$input_dir"/*.mp3; do
            kid3-cli -c "set date $year" "$i"
        done

        echo "done"
    fi 
}

## Use path appropriate to the host system in the directive below:
# shellcheck source=/home/adam/scripts/music_base/.venv/bin/activate
. "$activate_path" && cd "$python_pkg_dir" && python "$python_pkg" -d "$input_dir" -y "$iyaml" && deactivate && set_mp3_date && cd "$cur_dir" || exit

