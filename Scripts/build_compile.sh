


#!/bin/bash

compile_multi_java(){
    TIMEOUT=60
    compile_file="$1"
    now_cur_output="$2"
    now_working_dir="$3"
    output_file="$4"
    tep_PATH="$PATH"
    compile_res="FALSE"
    compile_version="None"
    export PATH="$ORACLEJAVA8:$tep_PATH"
    res8=$(timeout $TIMEOUT mvn clean compile --file "$compile_file" 2>&1)
    
    compile_info="ORACLEJAVA8:$res8"

    # echo "res8:$res8"
    if [[ $res8 == *"BUILD SUCCESS"* ]]
    then
        compile_res="TRUE"
        compile_version="ORACLEJAVA8"
    fi
    
    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$ORACLEJAVA11:$tep_PATH"
        res11=$(timeout $TIMEOUT mvn clean compile --file "$compile_file" 2>&1)
        # echo "res11:$res11"
        compile_info+="\n\n------------------------------------\n\n"
        compile_info+="ORACLEJAVA11:$res11"
        
        if [[ $res11 == *"BUILD SUCCESS"* ]]
        then
            compile_res="TRUE"
            compile_version="ORACLEJAVA11"
        fi

    fi
    
    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$ORACLEJAVA17:$tep_PATH"
        res17=$(timeout $TIMEOUT mvn clean compile --file "$compile_file" 2>&1)
        # echo "res17:$res17"
        compile_info+="\n\n------------------------------------\n\n"
        compile_info+="ORACLEJAVA17:$res17"
        if [[ $res17 == *"BUILD SUCCESS"* ]]
        then
            compile_res="TRUE"
            compile_version="ORACLEJAVA17"
        fi
    fi

    export PATH="$tep_PATH"
    final_res="$compile_res:$compile_version:$compile_info"
    now_cur_output+=",Build A $compile_res,$compile_version"
    echo "$now_cur_output" >> "$output_file"
    echo -e $compile_info > "$now_working_dir/compile_A_info"
    # -----------------------------------------------------
    # echo "$final_res"
}


T="TRUE"
F="FALSE"

# input csv path
conflict_file="clone.csv"

declare -a urls
declare -a project_names
declare -a commit_hashs
declare -a file_names
declare -a clone_results
declare -a strategies

declare -a args_compile_file
declare -a args_cur_output
declare -a args_working_dir


overall_dir="./projects"
if ! [[ -d $overall_dir ]]
then
    mkdir -p "$overall_dir"
fi
output_dir="./Data"
conflict_file="$output_dir/$conflict_file"
output_file="compile.csv"
output_file="$output_dir/$output_file"
output_first_line="url,project_name,commit,file_name,strategy"


while IFS=, read -r url project_name commit file_name strategy clone_result pass; do
    urls+=("$url")
    project_names+=("$project_name")
    commit_hashs+=("$commit")
    file_names+=("$file_name")
    strategies+=("$strategy")
    clone_result=$(echo "$clone_result" | tr -d '\r')
    clone_results+=("$clone_result")
done < "$conflict_file"


for ((i = 0; i < ${#urls[@]}; i++)); do
    line=$((i+1))
    cur_url="${urls[$i]}"
    cur_project_name=${project_names[$i]}
    cur_commit=${commit_hashs[$i]}
    cur_short_commit=$(echo "$cur_commit" | cut -c 1-7)
    cur_file_name=${file_names[$i]}
    cur_clone_result=${clone_results[$i]}
    cur_strategy=${strategies[$i]}
    cur_output="$cur_url,$cur_project_name,$cur_commit,$cur_file_name,$cur_strategy,$cur_clone_result"

    echo "url: ${cur_url}, project_name: ${cur_project_name}, commit: ${cur_commit}, file_name: ${cur_file_name}, strategy: ${cur_clone_result}"
    working_dir="$overall_dir/$cur_project_name-$cur_short_commit"
    if ! [[ -d $working_dir ]]
    then
        mkdir -p "$working_dir"
    fi


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
    
    echo "module_name:$module_name"
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



    A_B_commits=$(git -C "$working_dir/$cur_project_name" log --pretty=%P -n 1 $cur_commit)
    read A_commit B_commit <<< "$A_B_commits"
    echo "A_commit:$A_commit B_commit:$B_commit"
    base_commit=$(git -C "$working_dir/$cur_project_name" merge-base $A_commit $B_commit)
    echo "A_commit: $A_commit B_commit: $B_commit base_commit: $base_commit"

    if ! [[ -e "$working_dir/$version_A" ]]
    then
        echo "copying A" 
        cp -r "$working_dir/$cur_project_name" "$working_dir/$version_A"
    fi


    
    git -C "$working_dir/$version_A" checkout $A_commit 2>/dev/null
    echo "[PROCESS] Start compiling version A"
    # compile_multi_java $pom_path_A_test
    
    args_compile_file+=("$pom_path_A_test")
    args_cur_output+=("$cur_output")
    args_working_dir+=("$working_dir")
    

done
export -f  compile_multi_java
jobs=10
parallel  --jobs "$jobs" --xapply compile_multi_java ::: "${args_compile_file[@]}" ::: "${args_cur_output[@]}" ::: "${args_working_dir[@]}" ::: "$output_file"
wait