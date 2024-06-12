#!/bin/bash

compile_multi_java(){
    
    compile_file="$1"
    tep_PATH="$PATH"
    compile_res="FALSE"
    export PATH="$JAVA8:$tep_PATH"
    res8=$(mvn clean compile --file "$compile_file" 2>&1)
    
    compile_info="$res8"

    # echo "res8:$res8"
    if [[ $res8 == *"BUILD SUCCESS"* ]]
    then
        compile_res="TRUE"
    fi
    
    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$JAVA11:$tep_PATH"
        res11=$(mvn clean compile --file "$compile_file" 2>&1)
        # echo "res11:$res11"
        compile_info+="\n\n------------------------------------\n\n"
        compile_info+="$res11"
        
        if [[ $res11 == *"BUILD SUCCESS"* ]]
        then
            compile_res="TRUE"
        fi

    fi
    
    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$JAVA17:$tep_PATH"
        res17=$(mvn clean compile --file "$compile_file" 2>&1)
        # echo "res17:$res17"
        compile_info+="\n\n------------------------------------\n\n"
        compile_info+="$res17"
        if [[ $res17 == *"BUILD SUCCESS"* ]]
        then
            compile_res="TRUE"
        fi
    fi

    # local values=("$compile_res" "$compile_info")
    # echo "${values[@]}"
    export PATH="$tep_PATH"
    final_res="$compile_res:$compile_info"
    echo "$final_res"
}

parse_test_results(){
    success_symbol="BUILD SUCCESS"
    fail_symbol="BUILD FAILURE"
    test_res=$1
    output_str=""   
    if [[ $test_res == *"$success_symbol"* ]]
    then
        output_str+="TRUE"
    elif [[ $test_res == *"$fail_symbol"* ]]
    then
        output_str+="FALSE"
    fi
    # echo "$test_res"
    whole_sentence=$(echo "$test_res" | grep -o 'Tests run: [0-9]\+, Failures: [0-9]\+, Errors: [0-9]\+, Skipped: [0-9]\+'| tail -1)
    # echo "$whole_sentence"
    tests_run=$(echo "$whole_sentence" | grep -o 'Tests run: [0-9]\+' | grep -o '[0-9]\+')
    failures=$(echo "$whole_sentence" | grep -o 'Failures: [0-9]\+' | grep -o '[0-9]\+')
    errors=$(echo "$whole_sentence" | grep -o 'Errors: [0-9]\+' | grep -o '[0-9]\+')
    skipped=$(echo "$whole_sentence" | grep -o 'Skipped: [0-9]\+' | grep -o '[0-9]\+')
    # echo "$tests_run,$failures,$errors,$skipped"
    if [[ $test_res == *"Tests run:"* && $test_res == *"Failures:"* ]]
    then
        test_pass=$(expr "$tests_run" - "$failures" - "$errors" - "$skipped")
    fi
    output_str+=";RUN:${tests_run};FAILURE:${failures};ERROR:${errors};SKIP:${skipped};PASS:${test_pass}"
    echo "$output_str"   
}

test_multi_java(){
    compile_file="$1"
    tep_PATH="$PATH"
    compile_res="FALSE"
    export PATH="$JAVA8:$tep_PATH"
    res8=$(mvn test --file "$compile_file" 2>&1)
    res8=$(parse_test_results "$res8")
    compile_info="JAVA8:$res8"
    # echo "res8:$res8"
    if [[ $res8 == *"TRUE"* ]]
    then
        compile_res="TRUE"
    fi

    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$JAVA11:$tep_PATH"
        res11=$(mvn test --file "$compile_file" 2>&1)
        res11=$(parse_test_results "$res11")
        compile_info+=";JAVA11:$res11"
        
        if [[ $res11 == *"TRUE"* ]]
        then
            compile_res="TRUE"
        fi

    fi
    
    if [[ $compile_res == "FALSE" ]]
    then
        export PATH="$JAVA17:$tep_PATH"
        res17=$(mvn test --file "$compile_file" 2>&1)
        res17=$(parse_test_results "$res17")
        compile_info+=";JAVA17:$res17"
        if [[ $res17 == *"TRUE"* ]]
        then
            compile_res="TRUE"
        fi
    fi

    # local values=("$compile_res" "$compile_info")
    # echo "${values[@]}"
    export PATH="$tep_PATH"
    final_res="$compile_res:$compile_info"
    echo "$final_res"



}
add_test_dependency_for_pom(){
    xml_file="$1"

    evosuite_group_id="org.evosuite"
    evosuite_artifact_id="evosuite-standalone-runtime"
    evosuite_version="1.0.6"
    evosuite_scope="test"

    hamcrest_group_id="org.hamcrest"
    hamcrest_artifact_id="hamcrest-core"
    hamcrest_version="1.3"
    hamcrest_scope="test"




    dependencies_exists=$(xmlstarlet sel -t -c "/project/dependencies" $xml_file)

    if [[ -z "$dependencies_exists" ]]; then
        xmlstarlet ed -L -s "/project" -t elem -n "dependencies" $xml_file
    fi
    xmlstarlet ed -L -s "/project/dependencies" -t elem -n "dependency" $xml_file
    xmlstarlet ed -L -i "/project/dependencies/dependency[last()]" -t elem -n "groupId" -v "$evosuite_group_id" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "artifactId" -v "$evosuite_artifact_id" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "version" -v "$evosuite_version" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "scope" -v "$evosuite_scope" $xml_file

    xmlstarlet ed -L -s "/project/dependencies" -t elem -n "dependency" $xml_file
    xmlstarlet ed -L -i "/project/dependencies/dependency[last()]" -t elem -n "groupId" -v "$hamcrest_group_id" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "artifactId" -v "$hamcrest_artifact_id" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "version" -v "$hamcrest_version" $xml_file
    xmlstarlet ed -L -s "/project/dependencies/dependency[last()]" -t elem -n "scope" -v "$hamcrest_scope" $xml_file

}
modify_test_path_for_pom(){
    xml_file="$1"
    test_path="$2"
    build_exists=$(xmlstarlet sel -t -c "/project/build" $xml_file)

    if [[ -z "$build_exists" ]]; then
        xmlstarlet ed -L -s "/project" -t elem -n "build" $xml_file
    fi
    xmlstarlet ed -L -i "/project/build" -t elem -n "testSourceDirectory" -v "$test_path" $xml_file
}



T="TRUE"
F="FALSE"

declare -a urls
declare -a project_names
declare -a commit_hashs
declare -a file_names
declare -a strategies
declare -a clone_results
declare -a build_results
declare -a java_versions
declare -a others
conflict_file="test.csv"
consider_hash="none"
prefix=$(echo "$conflict_file" | cut -d '.' -f 1)
output_dir="./Data"
conflict_file="$output_dir/$conflict_file"
output_file="evosuite.csv"
output_file="$output_dir/$output_file"
output_first_line="url,project_name,commit,file_name,strategy"
current_contents=()
while IFS= read -r line
do
    current_contents+=("$line")
done < "$output_file"




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

# if [[ -e "$output_file" ]]
# then
#     rm "$output_file"
# fi

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


    overall_dir="./projects"

    if [[ "$consider_hash" != 'none' && "$cur_commit" != "$consider_hash" ]]
    then
        cur_output=${current_contents[$i]}
        if [[ i -eq 0 ]]
        then
            echo "$cur_output" > "$output_file"
        else
            echo "$cur_output" >> "$output_file"
        fi
        continue
    fi




    cur_output="$cur_url,$cur_project_name,$cur_commit,$cur_file_name,$cur_strategy,$cur_clone_result,$cur_build_result,$cur_java_version,$cur_other"

    if [[ "$cur_other" == *"Compile-middle-A-complete TRUE"* || "$cur_other" == *"Compile-middle-A-snippet TRUE"* ]] && [[ "$cur_other" == *"Compile-middle-B-complete TRUE"* || "$cur_other" == *"Compile-middle-B-snippet TRUE"* ]] 
    then
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
        else
            pom_path_A_test="$working_dir/$version_A/pom.xml"
            pom_path_A="$working_dir/$version_middle_A/pom.xml"
            pom_path_B="$working_dir/$version_middle_B/pom.xml"
            project_cp_A="$working_dir/$version_middle_A/target/classes"
            project_cp_B="$working_dir/$version_middle_B/target/classes"
        fi

        # -----------------------------------------------------
        # find commits
        A_B_commits=$(git -C "$working_dir/$cur_project_name" log --pretty=%P -n 1 $cur_commit)
        unset IFS
        read A_commit B_commit <<< "$A_B_commits"
        echo "A_commit:$A_commit B_commit:$B_commit"
        base_commit=$(git -C "$working_dir/$cur_project_name" merge-base $A_commit $B_commit)
        echo "A_commit: $A_commit B_commit: $B_commit base_commit: $base_commit"
        # -----------------------------------------------------
        TIMEOUT=80
        # -----------------------------------------------------
        
        export PATH="$ORACLEJAVA8:$PATH"
        export JAVA_HOME=$(echo "$ORACLEJAVA8" | sed 's|/bin$||')
        echo "$JAVA_HOME"
        dependency_res_A=$(mvn dependency:build-classpath --file ${pom_path_A} 2>&1)
        dependency_A_new=""
        if [[ "$dependency_res_A" == *"BUILD SUCCESS"* ]]
        then
            dependency_A=$(echo "$dependency_res_A" | sed -n '/\[INFO\] Dependencies classpath:/,/^\[INFO\]/p' | sed '/\[INFO\] Dependencies classpath:/d; /^\[INFO\]/d')
            IFS=":"
            read -ra array <<< "$dependency_A"
            for element in "${array[@]}"
            do
                if [[ $element == *".pom" ]]
                then
                    continue                    
                else
                    if [[ ! -z "$dependency_A_new" ]]
                    then
                        dependency_A_new="$dependency_A_new:$element"
                    else
                        dependency_A_new="$element"
                    fi
                fi

            done


        else
            dependency_A_new=""
        fi
        
        dependency_res_B=$(mvn dependency:build-classpath --file ${pom_path_B} 2>&1)
        dependency_B_new=""
        if [[ "$dependency_res_B" == *"BUILD SUCCESS"* ]]
        then
            dependency_B=$(echo "$dependency_res_B" | sed -n '/\[INFO\] Dependencies classpath:/,/^\[INFO\]/p' | sed '/\[INFO\] Dependencies classpath:/d; /^\[INFO\]/d')
            IFS=":"
            read -ra array <<< "$dependency_B"
            for element in "${array[@]}"
            do
                if [[ $element == *".pom" ]]
                then
                    continue                    
                else
                    if [[ ! -z "$dependency_B_new" ]]
                    then
                        dependency_B_new="$dependency_B_new:$element"
                    else
                        dependency_B_new="$element"
                    fi
                fi

            done

        else
            dependency_B_new=""
        fi

        if [ -n "$dependency_A_new" ]; 
        then
            total_project_cp_A="$project_cp_A:$dependency_A_new"
        else
            total_project_cp_A="$project_cp_A"
        fi

        if [ -n "$dependency_B_new" ]; 
        then
            total_project_cp_B="$project_cp_B:$dependency_B_new"
        else
            total_project_cp_B="$project_cp_B"
        fi


        # dependency_A=$(mvn dependency:build-classpath --file ${pom_path_A} | sed -n '/\[INFO\] Dependencies classpath:/,/^\[INFO\]/p' | sed '/\[INFO\] Dependencies classpath:/d; /^\[INFO\]/d')
        class_path="${cur_file_name#*src/main/java/}"
        class_path=$(echo "$class_path" | sed 's/\.java$//; s/\//./g' )
        echo "[PROCESS] Generating test cases for A"
        
        generate_res_A=$(java -jar evosuite-1.0.6.jar -seed 0 -class "${class_path}"  -projectCP "${total_project_cp_A}" -Dsearch_budget="$TIMEOUT" -Dtest_dir="$working_dir/$version_middle_A/evosuite_tests" 2>&1)
        if [[ $generate_res_A =~ ^.*Coverage\ of\ criterion\ LINE:\ ([0-9]+(\.[0-9]+)?)%.*$ && "$generate_res_A" == *"Computation finished"* ]]
        then
            echo "Generate A-middle success, continuing..."
            flag_A="TRUE"
        else
            echo "Generate A-middle failed, skipping..."
            flag_A="FALSE"
        fi
        line=$((i+1))
        # sed -i "$line s/$/,generate A $flag_A/" "$conflict_file"
        cur_output+=",generate A $flag_A"
        
        echo -e "$generate_res_A" > "$working_dir/evosuite_info"

        echo "[PROCESS] Generating test cases for B"
        generate_res_B=$(java -jar evosuite-1.0.6.jar -seed 0 -class "${class_path}"  -projectCP "${total_project_cp_B}" -Dsearch_budget="$TIMEOUT" -Dtest_dir="$working_dir/$version_middle_B/evosuite_tests" 2>&1)
        # echo "$generate_res_B"
        if [[ $generate_res_B =~ ^.*Coverage\ of\ criterion\ LINE:\ ([0-9]+(\.[0-9]+)?)%.*$ && "$generate_res_B" == *"Computation finished"* ]]
        then
            echo "Generate B-middle success, continuing..."
            flag_B="TRUE"
        else
            echo "Generate B-middle failed, skipping..."
            flag_B="FALSE"
        fi
        # sed -i "$line s/$/,generate B $flag_B/" "$conflict_file"
        cur_output+=",generate B $flag_B"
        echo -e "\n-------------\n" >> "$working_dir/$cur_project_name/evosuite_info"
        echo -e "$generate_res_B" >> "$working_dir/evosuite_info"

        if [[ i -eq 0 ]]
        then
            echo "$cur_output" > "$output_file"
        else
            echo "$cur_output" >> "$output_file"
        fi

    fi
done