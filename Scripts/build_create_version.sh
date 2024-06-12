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

conflict_file="conflict.csv"


overall_dir="./projects"
if ! [[ -d $overall_dir ]]
then
    mkdir -p "$overall_dir"
fi
output_dir="./Data"
conflict_file="$output_dir/$conflict_file"
output_file="create_versions.csv"
output_file="$output_dir/$output_file"
output_first_line="url,project_name,commit,file_name,strategy"

if [[ -e "$output_file" ]]
then
    conflict_file="$output_file"
fi

while IFS=, read -r url project_name commit file_name strategy clone_result build_result java_version other; do
    urls+=("$url")
    project_names+=("$project_name")
    commit_hashs+=("$commit")
    file_names+=("$file_name")
    strategies+=("$strategy")
    clone_results+=("$clone_result")
    build_results+=("$build_result")
    java_versions+=("$java_version")
    other=$(echo "$other" | tr -d '\r')
    others+=("$other")
done < "$conflict_file"

if [[ -e "$output_file" ]]
then
    rm "$output_file"
fi

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
    cur_java_version=${java_versions[$i]}
    cur_other=${others[$i]}
    cur_output="$cur_url,$cur_project_name,$cur_commit,$cur_file_name,$cur_strategy,$cur_clone_result,$cur_build_result,$cur_java_version,$cur_other"

    if [[ "$cur_other" == *"Compile-middle-A-complete TRUE"* || "$cur_other" == *"Compile-middle-A-snippet TRUE"* ]] && [[ "$cur_other" == *"Compile-middle-B-complete TRUE"* || "$cur_other" == *"Compile-middle-B-snippet TRUE"* ]] 
    then
        echo "already succeed!"
        echo "$cur_output" >> "$output_file"
        continue
    fi
    
    echo "url: ${cur_url}, project_name: ${cur_project_name}, commit: ${cur_commit}, file_name: ${cur_file_name}, strategy: ${cur_strategy}, other: ${cur_other}"


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

    
    # -----------------------------------------------------
    content_A=$(awk '/<<<<<<< HEAD/,/=======/{if (!/<<<<<<< HEAD/ && !/=======/) print};/<<<<<<< HEAD/{flag=1} />>>>>>>/{flag=0;next} flag==0{print}' "$working_dir/$version_M/$cur_file_name")
    content_B=$(awk '/=======/,/>>>>>>>/{if (!/=======/ && !/>>>>>>>/) print};/<<<<<<< HEAD/{flag=1} />>>>>>>/{flag=0;next} flag==0{print}' "$working_dir/$version_M/$cur_file_name")
    
    
    if ! [[ -e "$working_dir/$version_middle_A" ]]
    then
        cp -r "$working_dir/$version_M" "$working_dir/$version_middle_A"
    fi

    if [[ $cur_java_version == "ORACLEJAVA8" ]]
    then
        export PATH="$ORACLEJAVA8:$PATH"
    elif [[ $cur_java_version == "ORACLEJAVA11" ]]
    then
        export PATH="$ORACLEJAVA11:$PATH"
    elif [[ $cur_java_version == "ORACLEJAVA17" ]]
    then
        export PATH="$ORACLEJAVA17:$PATH"
    elif [[ $cur_java_version == "OPENJAVA8" ]]
    then
        export PATH="$OPENJAVA8:$PATH"
    elif [[ $cur_java_version == "OPENJAVA11" ]]
    then
        export PATH="$OPENJAVA11:$PATH"
    elif [[ $cur_java_version == "OPENJAVA17" ]]
    then
        export PATH="$OPENJAVA17:$PATH"
    fi



    echo "[PROCESS] Start compiling version A-middle"
    echo "[PROCESS] substitute the whole conflict file"
    echo "$content_A" > "$working_dir/$version_middle_A/$cur_file_name"
    
    res=$(mvn clean compile --file "$pom_path_A" 2>&1)
    if [[ $res == *"BUILD SUCCESS"* ]]
    then
        result_middle_A="TRUE"
    else
        result_middle_A="FALSE"
    fi

    if [[ "$result_middle_A" == "TRUE" ]]
    then
        # sed -i "$line s/$/,Compile-middle-A-snippet $result_middle_A/" "$conflict_file"
        cur_output+=",Compile-middle-A-snippet $result_middle_A"
    fi

    echo -e $res > "$working_dir/compile_middle_A_snippet"
    
    if [[ "$result_middle_A" == "FALSE" ]]
    then
        cp "$working_dir/$version_A/$cur_file_name" "$working_dir/$version_middle_A/$cur_file_name"
        res=$(mvn clean compile --file "$pom_path_A" 2>&1)
        if [[ $res == *"BUILD SUCCESS"* ]]
        then
            result_middle_A="TRUE"
        else
            result_middle_A="FALSE"
        fi


        echo -e $res > "$working_dir/compile_middle_A_complete"
        if [[ "$result_middle_A" == "TRUE" ]]
        then
            # sed -i "$line s/$/,Compile-middle-A-complete $result_middle_A/" "$conflict_file"
            cur_output+=",Compile-middle-A-complete $result_middle_A"
        fi
    fi

    if [[ $result_middle_A == "FALSE" ]]
    then
        echo "Compile A-middle failed"
        # sed -i "$line s/$/,Compile-middle-A $result_middle_A/" "$conflict_file"
        cur_output+=",Compile-middle-A $result_middle_A"
    else
        echo "Compile A-middle success"
    fi


    # prepare middle version for B
    if ! [[ -e "$working_dir/$version_middle_B" ]]
    then
        cp -r "$working_dir/$version_M" "$working_dir/$version_middle_B"
    fi
    echo "[PROCESS] Start compiling version B-middle"
    echo "[PROCESS] substitute the whole conflict file"
    echo "$content_B" > "$working_dir/$version_middle_B/$cur_file_name"
    res=$(mvn clean compile --file "$pom_path_B" 2>&1)
    if [[ $res == *"BUILD SUCCESS"* ]]
    then
        result_middle_B="TRUE"
    else
        result_middle_B="FALSE"
    fi
    if [[ "$result_middle_B" == "TRUE" ]]
    then
        # sed -i "$line s/$/,Compile-middle-B-snippet $result_middle_B/" "$conflict_file"
        cur_output+=",Compile-middle-B-snippet $result_middle_B"
    fi

    echo -e $res > "$working_dir/compile_middle_B_snippet"
    
    if [[ "$result_middle_B" == "FALSE" ]]
    then
        cp "$working_dir/$version_B/$cur_file_name" "$working_dir/$version_middle_B/$cur_file_name"
        res=$(mvn clean compile --file "$pom_path_B" 2>&1)
        if [[ $res == *"BUILD SUCCESS"* ]]
        then
            result_middle_B="TRUE"
        else
            result_middle_B="FALSE"
        fi
        echo -e $res > "$working_dir/compile_middle_B_complete"
        if [[ "$result_middle_B" == "TRUE" ]]
        then
            # sed -i "$line s/$/,Compile-middle-B-complete $result_middle_B/" "$conflict_file"
            cur_output+=",Compile-middle-B-complete $result_middle_B"
        fi
    fi

    if [[ $result_middle_B == "FALSE" ]]
    then
        echo "Compile B-middle failed"
        # sed -i "$line s/$/,Compile-middle-B $result_middle_B/" "$conflict_file"
        cur_output+=",Compile-middle-B $result_middle_B"
    else
        echo "Compile B-middle success"
    fi
    # -----------------------------------------------------
    echo "$cur_output" >> "$output_file"
done