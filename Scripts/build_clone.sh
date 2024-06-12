#!/bin/bash


declare -a urls
declare -a project_names
declare -a commit_hashs
declare -a file_names
declare -a strategies

overall_dir="./projects"
if ! [[ -d $overall_dir ]]
then
    mkdir -p "$overall_dir"
fi


conflict_file="inputs.csv"
# input file name
output_file="clone.csv"
# output file name 
output_dir="./Data"
conflict_file="$output_dir/$conflict_file"
output_file="$output_dir/$output_file"


while IFS=, read -r url project_name commit file_name strategy ; do
    urls+=("$url")
    project_names+=("$project_name")
    commit_hashs+=("$commit")
    file_names+=("$file_name")
    strategy=$(echo "$strategy" | tr -d '\r')
    strategies+=("$strategy")
done < "$conflict_file"


for ((i = 0; i < ${#urls[@]}; i++)); do
    cur_url="${urls[$i]}"
    cur_project_name=${project_names[$i]}
    cur_commit=${commit_hashs[$i]}
    cur_short_commit=$(echo "$cur_commit" | cut -c 1-7)
    cur_file_name=${file_names[$i]}
    cur_strategy=${strategies[$i]}


    echo "url: ${cur_url}, project_name: ${cur_project_name}, commit: ${cur_commit}, file_name: ${cur_file_name}, strategy: ${cur_strategy}"
    working_dir="$overall_dir/$cur_project_name-$cur_short_commit"
    if ! [[ -d $working_dir ]]
    then
        mkdir -p "$working_dir"
    fi

    cur_output="$cur_url,$cur_project_name,$cur_commit,$cur_file_name,$cur_strategy"


    echo "[PROCESS] Cloning ${cur_project_name}..."
    if ! [[ -e "$working_dir/$cur_project_name" ]]
    then
        clone_url=$(echo "$cur_url" | sed 's#https://github.com/#git@github.com:#')
        timeout $TIMEOUT git clone "$clone_url" "$working_dir/$cur_project_name" 2>&1
        if [ $? -eq 0 ]; then
            echo "Cloning successful"
            cur_output+="Clone TRUE,"
        else
            echo "Cloning failed: $result"
            cur_output+="Clone FALSE,"
        fi
    else
        echo "Already exists!"
        continue
    fi

    echo "$cur_output" >> "$output_file"
done
