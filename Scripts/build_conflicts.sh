#!/bin/bash


declare -a urls
declare -a project_names
declare -a commit_hashs
declare -a file_names
declare -a strategies
declare -a clone_results
declare -a build_results
declare -a java_versions
declare -a others

conflict_file="compile.csv"

overall_dir="./projects"
fi
if ! [[ -d $overall_dir ]]
then
    mkdir -p "$overall_dir"
fi


output_dir="./Data"
conflict_file="$output_dir/$conflict_file"
output_file="conflict.csv"
output_file="$output_dir/$output_file"
output_first_line="url,project_name,commit,file_name,strategy"


while IFS=, read -r url project_name commit file_name strategy clone_result build_result  other; do
    urls+=("$url")
    project_names+=("$project_name")
    commit_hashs+=("$commit")
    file_names+=("$file_name")
    strategies+=("$strategy")
    clone_results+=("$clone_result")
    build_results+=("$build_result")
    other=$(echo "$other" | tr -d '\r')
    others+=("$other")
done < "$conflict_file"


for ((i = 0; i < ${#urls[@]}; i++)); do
    line=$((i+1))
    cur_url="${urls[$i]}"
    cur_project_name=${project_names[$i]}
    cur_commit=${commit_hashs[$i]}
    cur_short_commit=$(echo "$cur_commit" | cut -c 1-7)
    cur_file_name=${file_names[$i]}
    cur_strategy=${strategies[$i]}
    cur_clone_result=${clone_results[$i]}
    cur_build_result=${build_results[$i]}
    cur_other=${others[$i]}
    echo "url: ${cur_url}, project_name: ${cur_project_name}, commit: ${cur_commit}, file_name: ${cur_file_name}, strategy: ${cur_strategy}"
    working_dir="$overall_dir/$cur_project_name-$cur_short_commit"
    if ! [[ -d $working_dir ]]
    then
        mkdir -p "$working_dir"
    fi

    if [[ "$cur_build_result" == *"FALSE"* ]]
    then
        echo "build failed, skipping..."
        continue
    fi
    cur_output="$cur_url,$cur_project_name,$cur_commit,$cur_file_name,$cur_strategy,$cur_clone_result,$cur_build_result,$cur_other"

    version_base="$cur_project_name-base"
    version_A="$cur_project_name-A"
    version_middle_A="$cur_project_name-middle-A"
    version_B="$cur_project_name-B"
    version_middle_B="$cur_project_name-middle-B"
    version_M="$cur_project_name-M"
    version_R="$cur_project_name-R"
    module_name="${cur_file_name%src/main/java*}"
    pom_path_A_total="$working_dir/$version_middle_A/pom.xml"
    pom_path_B_total="$working_dir/$version_middle_B/pom.xml"
    if [ "$module_name" == "/" ]; then
        module_name=""
    fi
    if [ -n "$module_name" ]; then
        pom_path_A_test="$working_dir/$version_A/${module_name}pom.xml"
        pom_path_A="$working_dir/$version_middle_A/${module_name}pom.xml"
        pom_path_B="$working_dir/$version_middle_B/${module_name}pom.xml"
        project_cp_A="$working_dir/$version_middle_A/${module_name}target/classes"
        project_cp_B="$working_dir/$version_middle_B/${module_name}target/classes"
        generated_path_A="$working_dir/$version_middle_A/${module_name}evosuite-tests"
        generated_path_B="$working_dir/$version_middle_B/${module_name}evosuite-tests"
    else
        pom_path_A_test="$working_dir/$version_A/pom.xml"
        pom_path_A="$working_dir/$version_middle_A/pom.xml"
        pom_path_B="$working_dir/$version_middle_B/pom.xml"
        project_cp_A="$working_dir/$version_middle_A/target/classes"
        project_cp_B="$working_dir/$version_middle_B/target/classes"
        generated_path_A="$working_dir/$version_middle_A/evosuite-tests"
        generated_path_B="$working_dir/$version_middle_B/evosuite-tests"
    fi

    # -----------------------------------------------------
    # find commits
    A_B_commits=$(git -C "$working_dir/$cur_project_name" log --pretty=%P -n 1 $cur_commit)
    read A_commit B_commit <<< "$A_B_commits"
    echo "A_commit:$A_commit B_commit:$B_commit"
    base_commit=$(git -C "$working_dir/$cur_project_name" merge-base $A_commit $B_commit)
    echo "A_commit: $A_commit B_commit: $B_commit base_commit: $base_commit"
    # -----------------------------------------------------



    

    if ! [[ -e "$working_dir/$version_base" ]]
    then
        echo "copying base"
        cp -r "$working_dir/$cur_project_name" "$working_dir/$version_base"
        git -C "$working_dir/$version_base" checkout $base_commit 2>/dev/null
    fi

    if ! [[ -e "$working_dir/$version_B" ]]
    then
        echo "copying B"
        cp -r "$working_dir/$cur_project_name" "$working_dir/$version_B"
        git -C "$working_dir/$version_B" checkout $B_commit 2>/dev/null
    fi

    if ! [[ -e "$working_dir/$version_M" ]]
    then
        echo "copying M"
        cp -r "$working_dir/$cur_project_name" "$working_dir/$version_M"
    fi   

    if ! [[ -e "$working_dir/$version_R" ]]
    then
        echo "copying R"
        cp -r "$working_dir/$cur_project_name" "$working_dir/$version_R"
        git -C "$working_dir/$version_R" checkout $cur_commit 2>/dev/null
    fi   
    # -----------------------------------------------------

    # -----------------------------------------------------
    echo "[PROCESS] Merge A and B to get M"
    git_status=$(git -C "$working_dir/$version_M" status  2>&1)
    if [[ $git_status == *"fix conflicts"* ]]
    then
        echo "Already conflicts!"
    else
        git -C "$working_dir/$version_M" checkout $A_commit 2>/dev/null
        merge_res=$(git -C "$working_dir/$version_M" merge $A_commit $B_commit)
        conflict_str="CONFLICT"
        # echo "$merge_res"
        # echo "merge result:$merge_res"
        if [[ $merge_res == *"$conflict_str"* ]]
        then
            # sed -i "$line s/$/,Conflicts Happen/" "$conflict_file"
            cur_output+=",Conflicts TRUE"
            echo -e "$merge_res" > "$working_dir/merge_conflicts_info"
            echo "Merge conflicts happen."
        else
            # sed -i "$line s/$/,Conflicts Not Happen/" "$conflict_file"
            cur_output+=",Conflicts FALSE"
            echo -e "$merge_res" > "$working_dir/merge_conflicts_info"
            echo "Merge conflicts do not happen."
            continue
        fi
    fi
    echo "$cur_output" >> "$output_file"
   
done