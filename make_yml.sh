#!/bin/bash

## This script has been verified with `schellcheck`
##
## Make generating xspf playlist easier:
## - Adjust paths on lines 32-35
## - Adjust `source=` on line 107
## - Create a symbolic link to this script file, e.g.;
##   ```
##   sudo ln -s /home/user/scripts/music_base/make_yml.sh /home/user/scripts/make-yml
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
python_pkg_dir="$HOME/scripts/music_base"
python_pkg="$python_pkg_dir/meta_getter.py"

# echo "activation path: $activate_path"

Usage() {
    echo "This program creates a YAML file in the directory specified by the parameter -d and the same "
    echo "name as the directory.                                                                       "
    echo "The directory name is expected to be named on the pattern (use underscores in placde of      "
    echo "spaces):                                                                                     "
    echo "   {artist_name}_-_[{year}]_{album_title}                                                    "
    echo "                                                                                             "
    echo "Usage:                                                                                       "
    echo "    -d target directory containing audio files -- the output file is to be placed there      " 
    echo "    -m (optional) indicates the number of tracks on the album, possible values:              "
    echo "       0 - the underlying program counts the audio files in -d to identify the correct DB    "
    echo "           record                                                                            "
    echo "       1 or higher - the expected number of tracks (files in -d are not counted)             "
    echo "       absent (parameter is not provided) - the number of files is not checked               "
    echo "       directory.                                                                            "
    echo "    -r search query, if not provided, the program crreates it from the name of -d (artist,   "
    echo "       title)                                                                                "
    echo "    -a artist's name (band name) surrounded by double quotes; if absent, extracted from the  "
    echo "       name of -d                                                                            "
    echo "    -t album title surrounded by double quotes; if absent, extracted from the name of -d     "
    echo "    -y the release year of the album                                                         "
    echo "    --help                                                                                   "
}

if [[ $# -lt 1 ]]; then
    echo "Insufficient arguments ... "
    echo ""
    Usage
    exit 1
fi

to_match=0
query_str=""
artist=""
title=""
year=0

while [[ $# -gt 0 ]];
do
    case "$1" in
        -d|--idir)
            idir="$2"
            shift
            ;;
        -m|--files_to_match)
            to_match="$2"
            shift
            ;;
        -r|--query_str)
            query_str="$2"
            shift
            ;;
        -a|--artist)
            artist="$2"
            shift
            ;;
        -t|--title)
            title="$2"
            shift
            ;;
        -y|--year)
            year="$2"
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

cur_dir=$(pwd)

source "$activate_path" && cd "$python_pkg_dir" && python "$python_pkg" -d "$input_dir" -y "$year" -m "$to_match" -a "$artist" -t "$title" -r "$query_str" && deactivate && cd "$cur_dir" || exit
