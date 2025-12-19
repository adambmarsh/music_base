#!/bin/bash

## This script has been verified with `shellcheck`
##
## - Create a symbolic link to this script file, e.g.;
##   ```
##   sudo ln -s /home/user/scripts/flask_music_search/music-search.sh /home/user/scripts/music-search
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

run_dir="$HOME/scripts/music_base/"
activate_path="$run_dir/.venv/bin/activate"

# echo "activation path: $activate_path"

Usage() {
    echo "This script searches for a string or regex pattern in audio tags.                            "
    echo "Usage:                                                                                       "
    echo "    -d directory in which to search                                                          "
    echo "    -f find, the text to find or a regex pattern (remember to provide -x with a value        "
    echo "    -l max number of albums/sub-directories to search, unlimited if not given                "
    echo "    -x If provided and the value evaluates to True, a regex search is used                   "
    echo "    --help                                                                                   "
}

while [[ $# -gt 0 ]];
do
    case "$1" in
        -d|--start_dir)
            start_place="$2"
            shift
            ;;
        -f|--search_text)
            what="$2"
            shift
            ;;
        -l|--limit)
            limit="$2"
            shift
            ;;
        -x|--use_rx)
            use_rx="$2"
            shift
            ;;
        --help|*)
            Usage
            exit 1
            ;;
    esac
    shift
done

if [ -z "$what" ]; then
    echo "Search criteria missing, exiting"
    exit 1
fi

if [ -z "$start_place" ]; then
    start_place="$(pwd)"
fi

if [ -z "$limit" ]; then
    limit=-1
fi


if [ -z "$use_rx" ]; then
    use_rx="False"
fi

echo "what=""$what"
echo "start=""$start_place"
echo "limit=""$limit"
echo "use_rx=""$use_rx"

. "$activate_path" && cd "$run_dir" && python ./music_meta_search.py -d "$start_place" -f "$what" -l "$limit" -x "$use_rx" && deactivate
