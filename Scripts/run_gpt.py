from openai import OpenAI
import csv
import os
import re
import xml.etree.ElementTree as ET
import subprocess
import copy
from tqdm import tqdm
import traceback
import sys
temperature = 0.7
max_iter = 20
feedback_thre = 10 + 1
whether_save = sys.argv[1]
override = sys.argv[2]


consider_hash = None


def extract_java_tags(text):
    pattern = r'```java(.*?)```'
    result = re.findall(pattern, text, flags=re.DOTALL)
    return result
def find_test_classes(code):
    pattern = r'public\s+class\s+\w*Test\w*\s*{.*}'
    matches = re.findall(pattern, code, re.DOTALL)
    test_class = matches[0] 

    package_pattern = r"package\s+[\w\.]+;"
    import_pattern = r"(import(\s+static)?\s+[\w\.]+(\.\*)?;)"

    import_states = re.findall(import_pattern, code)
    package_states = re.findall(package_pattern, code)
    import_states = [x[0] for x in import_states]

    import_package_states = package_states + import_states

    return '\n'.join(import_package_states) + '\n' + test_class
def extract_last_test_results(text):
    pattern = r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)'

    matches = re.findall(pattern, text)

    if matches:
        last_match = matches[-1]
        tests_run, failures, errors, skipped = last_match
        return {
            'RUN': int(tests_run),
            'FAILURE': int(failures),
            'ERROR': int(errors),
            'SKIP': int(skipped),
            'PASS': int(tests_run) - int(failures) - int(errors) - int(skipped)
        }
    else:
        return {
            'RUN': 'none',
            'FAILURE': 'none',
            'ERROR': 'none',
            'SKIP': 'none',
            'PASS': 'none'
        }
def parse_test_results(raw_res):
    success_symbol="BUILD SUCCESS"
    fail_symbol="BUILD FAILURE"
    output_str = ""
    if success_symbol in raw_res:
        output_str = "SUCCESS"
    elif fail_symbol in raw_res:
        output_str = "FAIL"
    parse_output = extract_last_test_results(raw_res)
    for each in parse_output:
        output_str += ';%s:%s'%(each, parse_output[each])
    return output_str
def execute_command(cmd):
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout
    if output == '':
        output = "ERROR:%s"%result.stderr
    return output
def add_dependency_to_pom(pom_file, group_id, artifact_id, version, scope):

    # Parse the XML file
    tree = ET.parse(pom_file)
    root = tree.getroot()

    # Find the dependencies section
    dependencies = root.find("./{http://maven.apache.org/POM/4.0.0}dependencies")
    if dependencies is None:
        dependencies = ET.SubElement(root, "{http://maven.apache.org/POM/4.0.0}dependencies")
    
    have_junit = False
    for dependency in dependencies:
        cur_group_id = dependency.find('{http://maven.apache.org/POM/4.0.0}groupId')
        cur_artifact_id = dependency.find('{http://maven.apache.org/POM/4.0.0}artifactId')
        cur_version = dependency.find('{http://maven.apache.org/POM/4.0.0}version')
        # if not cur_artifact_id is None:
        #     print(cur_artifact_id.text)
        try:
            if "junit" == cur_group_id.text.lower() and  "junit" == cur_artifact_id.text.lower():
                if not cur_version is None:
                    version_text = cur_version.text
                    version_text = version_text.split('.')
                    if int(version_text[0]) < 4 or (int(version_text[0]) == 4 and int(version_text[1]) < 11):
                        cur_version.text = '4.11'
                have_junit = True
        except:
            pass
    if have_junit == False:
        # Create a new dependency element
        junit_dependency = ET.Element("{http://maven.apache.org/POM/4.0.0}dependency")

        # Create the group id element and set its text
        group_id_element = ET.SubElement(junit_dependency, "groupId")
        group_id_element.text = 'junit'

        # Create the artifact id element and set its text
        artifact_id_element = ET.SubElement(junit_dependency, "artifactId")
        artifact_id_element.text = 'junit'

        # Create the version element and set its text
        version_element = ET.SubElement(junit_dependency, "version")
        version_element.text = '4.11'

        scope_element = ET.SubElement(junit_dependency, "scope")
        scope_element.text = 'test'

        # Append the new dependency to the dependencies section
        dependencies.append(junit_dependency)


    have_dependency = False 
    for dependency in dependencies:
        cur_group_id = dependency.find('{http://maven.apache.org/POM/4.0.0}groupId')
        cur_artifact_id = dependency.find('{http://maven.apache.org/POM/4.0.0}artifactId')
        cur_version = dependency.find('{http://maven.apache.org/POM/4.0.0}version')
        # if not cur_artifact_id is None:
        #     print(cur_artifact_id.text)
        try:
            if group_id == cur_group_id.text.lower() and artifact_id == cur_artifact_id.text.lower():
                have_dependency = True
        except:
            pass

    if have_dependency == False:

        # Create a new dependency element
        new_dependency = ET.Element("{http://maven.apache.org/POM/4.0.0}dependency")

        # Create the group id element and set its text
        group_id_element = ET.SubElement(new_dependency, "groupId")
        group_id_element.text = group_id

        # Create the artifact id element and set its text
        artifact_id_element = ET.SubElement(new_dependency, "artifactId")
        artifact_id_element.text = artifact_id

        # Create the version element and set its text
        version_element = ET.SubElement(new_dependency, "version")
        version_element.text = version

        scope_element = ET.SubElement(new_dependency, "scope")
        scope_element.text = scope

        # Append the new dependency to the dependencies section
        dependencies.append(new_dependency)
    # for elem in root.iter():
    #     if '}' in elem.tag and 'project' not in elem.tag:
    #         elem.tag = elem.tag.split('}', 1)[1]
    # Write the modified XML back to the file without namespace prefix
    tree.write(pom_file, xml_declaration=True, encoding='UTF-8', default_namespace='')


def add_test_source_directory_to_pom(pom_file_path, test_source_directory):
    # Parse the XML file
    tree = ET.parse(pom_file_path)
    root = tree.getroot()

    # Check if 'build' element exists
    build = root.find("./{http://maven.apache.org/POM/4.0.0}build")

    # If 'build' element doesn't exist, create it
    if build is None:
        build = ET.SubElement(root, "{http://maven.apache.org/POM/4.0.0}build")

    test_source_dir = ET.SubElement(build, "{http://maven.apache.org/POM/4.0.0}testSourceDirectory")
    
    # Set the text of 'testSourceDirectory' element
    test_source_dir.text = test_source_directory

    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    # Write the modified XML back to the file
    tree.write(pom_file_path, xml_declaration=True, encoding='UTF-8')

def obtain_conflicts(lines):
    conflict_start_re = re.compile(r'<<<<<<<.*')
    conflict_sep_re = re.compile(r'=======.*')
    conflict_end_re = re.compile(r'>>>>>>>.*')

    in_conflict = False
    total_conflicts = []
    cur_conflict = []
    for line in lines:
        if conflict_start_re.match(line):
            in_conflict = True
            cur_conflict = []
            cur_conflict.append(line)
        elif conflict_end_re.match(line):
            in_conflict = False
            cur_conflict.append(line)
            total_conflicts.append(''.join(cur_conflict))
        else:
            if in_conflict:
                cur_conflict.append(line)

    return total_conflicts

def extract_class_name(code):
    match = re.search(r"public\s+class\s+(\w+Test\w*)\s*\{", code)
    if match:
        return match.group(1)  
    else:
        return None



if __name__ == '__main__':
    OPENAI_API_KEY="your_api_key" 
    client = OpenAI(api_key=OPENAI_API_KEY)
    result_path = './merge'
    csv_path = "./merge"


    file = 'evosuite_test.csv'
    

    init_prompt_template = "You are an expert at writing unit test cases for Java and at understanding the merge conflicts. \n\nConflicting snippet:\n\n{}\n\nWe provide a conflicting snippet above, the contents between <<<<<<< and ======= are from version A, and the contents between ======= and >>>>>>> are from version B. To help understand the conflict, we provide the whole class where the conflicts are located. \n\nThe whole class:\n\n{}\n\n Instruction:  Please write one unit test case for the conflicting method of each version, which can reveal the semantics of each version. The names of the test classes are \"${{class_name}}TestV1\" and \"${{class_name}}TestV2\", \"$class_name\" is the name of the class under test. Please generate the tests using Junit4. Don't generate the package declaration statement. Please generate the test class for version A and version B separately, and first generate for version A and then generate for version B. Use ```java``` to surround the test class of two versions separately, and Don't use ```java``` to surround other things except the test classes of version A and B."
    
    
    same_prompt = "The test generated for version {} can pass on both version A and version B. It cannot distinguish between the two versions. Please generate a new test that can reveal the semantics of version {} and distinguish between the two versions. The requirements are the same to the previous. Please generate the import statements and the test class for version {} and use ```java``` to surround the code. Don't use ```java``` to surround other things except the test class."
                        
    
    total_contents_csv = csv.reader(open('%s/%s'%(csv_path, file), 'r', newline=''))
    total_contents = []
    for row in total_contents_csv:
        total_contents.append(row)


    total_results = []
    csv_f = open('%s/gpt.csv'%(csv_path), 'w', newline='')
    writer = csv.writer(csv_f)
    for i in tqdm(range(len(total_contents))):

        each = total_contents[i]
        url = each[0]
        project_name = each[1]
        hash = each[2]
        java_version = each[7]

        if consider_hash != None and hash != consider_hash:
            if whether_save == 'true':
                writer.writerow(total_contents[i])
                csv_f.flush()
            continue
        short_commit_hash = hash[:7]
        file_name = each[3]
        strategy = each[4]
        pre_gpt_res = False
        special_comment = False
        for each_item in each:
            if "Evosuite:True" in each_item:
                pre_gpt_res = True
            if "comment" in each_item:
                special_comment = True
        if pre_gpt_res:
            if whether_save == 'true':
                writer.writerow(total_contents[i])
                csv_f.flush()
            continue
        if special_comment:
            if whether_save == 'true':
                writer.writerow(total_contents[i])
                csv_f.flush()
            continue
        print('Processsing %s-%s'%(project_name, short_commit_hash))
        
        class_path = re.search(r'src/main/java/(.*)', file_name).group(1)[:-5]
        version_middle_A="%s-middle-A"%project_name
        version_middle_B="%s-middle-B"%project_name
        version_middle_base="%s-middle-base"%project_name
        version_M="%s-M"%project_name
        version_R="%s-R"%project_name

        overall_dir="./merge/projects"
        module_name = re.search(r'(.*)/src/main/java', file_name)
        path = '%s/%s-%s' % (overall_dir, project_name, short_commit_hash)
        

        if module_name:
            module_name = module_name.group(1)

            A_path = '%s/%s/%s' % (path, version_middle_A, module_name)
            B_path = '%s/%s/%s' % (path, version_middle_B, module_name)
            base_path = '%s/%s/%s' % (path, version_middle_base, module_name)
        else:
            A_path = '%s/%s' % (path, version_middle_A)
            B_path = '%s/%s' % (path, version_middle_B)
            base_path = '%s/%s' % (path, version_middle_base)

        if not os.path.exists('%s/%s'%(base_path, 'pom_backup.xml')):
            os.system('cp %s/pom.xml %s/pom_backup.xml'%(base_path, base_path))
        PATH = os.environ.get('PATH')
        JAVA = os.environ.get(java_version)
        JAVA_HOME = JAVA[:JAVA.index('/bin')]
        os.environ['PATH'] = '%s:%s'%(JAVA, PATH)
        os.environ['JAVA_HOME'] = JAVA_HOME
        os.system('echo $JAVA_HOME')

        overall_dir="./merge/projects"
        project_path = '%s/%s-%s' % (overall_dir, project_name, short_commit_hash)
        gpt_path_A = "%s/%s/gpt_tests_A"%(project_path, version_middle_A)
        gpt_path_B = "%s/%s/gpt_tests_B"%(project_path, version_middle_B)
        if not os.path.exists(gpt_path_A):
            os.makedirs(gpt_path_A)
        if not os.path.exists(gpt_path_B):
            os.makedirs(gpt_path_B)

        test_class = file_name.split('/')[-1].split('.')[0]
        test_class_A = "%s_TestA"%test_class
        test_class_B = "%s_TestB"%test_class

        

        try:
            gpt_src = '%s/gpt_src'%(project_path)
            if override == 'true':
                if os.path.exists('%s/gpt_traceback'%(gpt_src)):
                    os.remove('%s/gpt_traceback'%(gpt_src))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_A_test_A')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_A_test_A'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_B_test_A')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_B_test_A'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_A_test_B')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_A_test_B'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_B_test_B')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_B_test_B'))
            diff_file_path = "%s/diff_conflict-%s.java"%(project_path, test_class)
            diff_contents = open(diff_file_path).read()
            diff_contents_lines = open(diff_file_path).readlines()
            conflict_contents = obtain_conflicts(diff_contents_lines)

            existing_tests_path = file_name.replace('src/main/java', 'src/test/java').replace('.java', 'Test.java')

            existing_tests_path = '%s/%s/%s'%(project_path, version_middle_A, existing_tests_path)

            if os.path.exists(existing_tests_path):
                existing_tests = open(existing_tests_path).read()
            else:
                existing_tests = ''
            cur_init_prompt = init_prompt_template.format('\n\n'.join(conflict_contents), diff_contents)
            messages = []
            messages.append({"role": "system", "content": "You are an expert at writing unit test cases for Java and at understanding the merge conflicts."})
            messages.append({"role": "user", "content": cur_init_prompt})

            
            if not os.path.exists(gpt_src):
                os.makedirs(gpt_src)
            with open('%s/%s'%(gpt_src, 'init_prompt'), 'w') as f:
                f.write(cur_init_prompt)
            p = open('%s/talk_process'%gpt_src, 'w')
            p.write('\n-----------------User-----------------\n')
            p.write(cur_init_prompt)
            p.flush()
            print('Initial query starting...')
            completion = client.chat.completions.create(
                model="gpt-4-turbo",
                temperature=temperature,
                messages=messages
            )
            print('Initial query finished.')
            if override == 'true':
                if os.path.exists('%s/gpt_traceback'%(gpt_src)):
                    os.remove('%s/gpt_traceback'%(gpt_src))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_A_test_A')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_A_test_A'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_B_test_A')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_B_test_A'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_A_test_B')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_A_test_B'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_B_test_B')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_B_test_B'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_base_test_A')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_base_test_A'))
                if os.path.exists('%s/%s'%(project_path, 'gpt_code_base_test_B')):
                    os.remove('%s/%s'%(project_path, 'gpt_code_base_test_B'))


            gpt_output = completion.choices[0].message.content
            p.write('\n-----------------Assistant-----------------\n')
            
            p.write('%s'%(gpt_output))     
            messages.append({"role": "assistant", "content": gpt_output})
            gpt_output = extract_java_tags(gpt_output)
            if len(gpt_output) == 1:
                class_name = extract_class_name(gpt_output[0])
                if 'V1' in class_name:
                    test_A = gpt_output[0]
                    test_B = None
                    class_name_A = class_name
                    class_name_B = None
                elif 'V2' in class_name:
                    test_A = None
                    test_B = gpt_output[0]
                    class_name_A = None
                    class_name_B = class_name
            else:
                test_A, test_B = gpt_output[0], gpt_output[1]
                # test_A = find_test_classes(test_A)
                # test_B = find_test_classes(test_B)


                class_name_A = extract_class_name(test_A)
                class_name_B = extract_class_name(test_B)


            package_pattern = r"package\s+[\w\.]+;"
            import_pattern = r"(import(\s+static)?\s+[\w\.]+(\.\*)?;)"

            
            import_states = re.findall(import_pattern, diff_contents)
            package_states = re.findall(package_pattern, diff_contents)
            import_states = [x[0] for x in import_states]

            import_package_states = package_states + import_states
            import_package_states.append('import static org.junit.Assert.*;')
            if test_A:
                test_A = '\n'.join(import_package_states) + '\n' + test_A
            if test_B:
                test_B = '\n'.join(import_package_states) + '\n' + test_B
            p.flush()    
            if test_A:
                open('%s/%s.java'%(gpt_path_A, class_name_A), 'w').write(test_A)
            if test_B:
                open('%s/%s.java'%(gpt_path_B, class_name_B), 'w').write(test_B)
            if test_A == None:
                total_contents[i].append('gpt_code_A_test_A:empty')
                total_contents[i].append('gpt_code_B_test_A:empty')
            else:
                A_messages = copy.deepcopy(messages)
                # for k in range(feedback_thre):
                A_feedback_thre = feedback_thre
                k = 0
                while True:
                    if os.path.exists("%s/pom_backup.xml"%A_path):
                        os.system("cp %s/pom_backup.xml %s/pom.xml"%(A_path, A_path))

                    add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                    add_test_source_directory_to_pom('%s/pom.xml'%A_path, test_source_directory=gpt_path_A)
                    output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(A_path, class_name_A))        
                    output_str = parse_test_results(output)
                    if 'SUCCESS' in output_str or k == A_feedback_thre - 1 or k == max_iter:
                        if os.path.exists("%s/pom_backup.xml"%B_path):
                            os.system("cp %s/pom_backup.xml %s/pom.xml"%(B_path, B_path))

                        add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                        add_test_source_directory_to_pom('%s/pom.xml'%B_path, test_source_directory=gpt_path_A)
                        B_A_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(B_path, class_name_A))
                        B_A_output_str = parse_test_results(B_A_output)
                        if k == max_iter:
                            with open('%s/%s'%(project_path, 'gpt_code_A_test_A'), 'w') as f:
                                f.write(output)
                            total_contents[i].append('gpt_code_A_test_A:%s'%output_str)

                            with open('%s/%s'%(project_path, 'gpt_code_B_test_A'), 'w') as f:
                                f.write(B_A_output)
                            total_contents[i].append('gpt_code_B_test_A:%s'%B_A_output_str)

                            if os.path.exists("%s/pom_backup.xml"%base_path):
                                os.system("cp %s/pom_backup.xml %s/pom.xml"%(base_path, base_path))
                            add_dependency_to_pom('%s/pom.xml'%base_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                            add_test_source_directory_to_pom('%s/pom.xml'%base_path, test_source_directory=gpt_path_A)
                            base_A_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(base_path, class_name_A))        
                            base_A_output_str = parse_test_results(base_A_output)
                            total_contents[i].append('gpt_code_base_test_A:%s'%base_A_output_str)
                            with open('%s/%s'%(project_path, 'gpt_code_base_test_A'), 'w') as f:
                                f.write(base_A_output)
                            break
                        if 'SUCCESS' in output_str and 'SUCCESS' in B_A_output_str:
                            cur_same_prompt = same_prompt.format('A', 'A', 'A')
                            p.write('\n-----------------User(success but same)-----------------\n')
                            p.write(cur_same_prompt)
                            p.flush()
                            A_messages.append({"role": "user", "content": cur_same_prompt})
                            print('A Feedback (success but same) %s starting...'%k)
                            completion = client.chat.completions.create(
                                model="gpt-4-turbo",
                                # response_format={ "type": "json_object" },
                                temperature=temperature,
                                messages=A_messages
                            )
                            print('A Feedback %s end...'%k)
                            gpt_output = completion.choices[0].message.content
                            p.write('\n-----------------Assistant-----------------\n')
                            p.write(gpt_output)   
                            p.flush()
                            A_messages.append({"role": "assistant", "content": gpt_output})
                            gpt_output = extract_java_tags(gpt_output)
                            if len(gpt_output) > 0:
                                gpt_output = gpt_output[0]
                            # gpt_output = find_test_classes(gpt_output)
                            
                                os.system('rm %s/%s.java'%(gpt_path_A, class_name_A))
                                test_A = gpt_output
                                class_name_A = extract_class_name(test_A)
                                # print(test_A)
                                test_A = '\n'.join(import_package_states) + '\n' + test_A
                                open('%s/%s.java'%(gpt_path_A, class_name_A), 'w').write(test_A)
                            else:
                                pass
                            A_feedback_thre += k + 1
                            k += 1
                            continue
                        else:
                            with open('%s/%s'%(project_path, 'gpt_code_A_test_A'), 'w') as f:
                                f.write(output)
                            total_contents[i].append('gpt_code_A_test_A:%s'%output_str)

                            with open('%s/%s'%(project_path, 'gpt_code_B_test_A'), 'w') as f:
                                f.write(B_A_output)
                            total_contents[i].append('gpt_code_B_test_A:%s'%B_A_output_str)
                            if os.path.exists("%s/pom_backup.xml"%base_path):
                                os.system("cp %s/pom_backup.xml %s/pom.xml"%(base_path, base_path))
                            add_dependency_to_pom('%s/pom.xml'%base_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                            add_test_source_directory_to_pom('%s/pom.xml'%base_path, test_source_directory=gpt_path_A)
                            base_A_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(base_path, class_name_A))        
                            base_A_output_str = parse_test_results(base_A_output)
                            total_contents[i].append('gpt_code_base_test_A:%s'%base_A_output_str)
                            with open('%s/%s'%(project_path, 'gpt_code_base_test_A'), 'w') as f:
                                f.write(base_A_output)
                            break
                    error_msg = execute_command("echo '%s' | grep '\[ERROR\]' | grep -v 'Please refer to' | grep -v '\[Help 1\]' | grep -v '> \[Help 1\]' | grep -v 'To see the full stack trace' | grep -v 'Re-run Maven using the -X switch' | grep -v 'For more information about the errors'"%output)
                    error_prompt = "The test for version A has some bugs. Please repair the bugs and return the complete test method after repair. The requirements are the same to the previous. The names of the test classes are \"${{class_name}}TestV1\", \"$class_name\" is the name of the class under test. Please generate the tests using Junit4. Don't generate the package declaration statement. Please generate the import statements and the test class for version A and use ```java``` to surround the code. Don't use ```java``` to surround other things except the test class.\n\nError message:\n\n%s"%error_msg 
                    p.write('\n-----------------User-----------------\n')
                    p.write(error_prompt)
                    p.flush()
                    A_messages.append({"role": "user", "content": error_prompt})
                    print('A Feedback %s starting...'%k)
                    completion = client.chat.completions.create(
                        model="gpt-4-turbo",
                        # response_format={ "type": "json_object" },
                        temperature=temperature,
                        messages=A_messages
                    )
                    print('A Feedback %s end...'%k)
                    gpt_output = completion.choices[0].message.content
                    p.write('\n-----------------Assistant-----------------\n')
                    p.write(gpt_output)   
                    p.flush()
                    A_messages.append({"role": "assistant", "content": gpt_output})
                    gpt_output = extract_java_tags(gpt_output)
                    if len(gpt_output) > 0:
                        gpt_output = gpt_output[0]
                        # gpt_output = find_test_classes(gpt_output)
                        os.system('rm %s/%s.java'%(gpt_path_A, class_name_A))
                        test_A = gpt_output
                        class_name_A = extract_class_name(test_A)
                        # print(test_A)
                        test_A = '\n'.join(import_package_states) + '\n' + test_A
                        open('%s/%s.java'%(gpt_path_A, class_name_A), 'w').write(test_A)
                    else:
                        pass
                    k += 1

            p.write('\n\n==============================B starts==============================\n\n')
            p.flush()
            if test_B == None:
                total_contents[i].append('gpt_code_A_test_B:empty')
                total_contents[i].append('gpt_code_B_test_B:empty')
            else:
                B_messages = copy.deepcopy(messages)
                B_feedback_thre = feedback_thre
                k = 0
                # for k in range(feedback_thre):
                while True:
                    if os.path.exists("%s/pom_backup.xml"%B_path):
                        os.system("cp %s/pom_backup.xml %s/pom.xml"%(B_path, B_path))
                    add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                    add_test_source_directory_to_pom('%s/pom.xml'%B_path, test_source_directory=gpt_path_B)
                    output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(B_path, class_name_B))
                    output_str = parse_test_results(output)
                    if 'SUCCESS' in output_str or k == B_feedback_thre - 1 or k == max_iter:
                        if os.path.exists("%s/pom_backup.xml"%A_path):
                            os.system("cp %s/pom_backup.xml %s/pom.xml"%(A_path, A_path))

                        add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                        add_test_source_directory_to_pom('%s/pom.xml'%A_path, test_source_directory=gpt_path_B)
                        A_B_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(A_path, class_name_B))
                        A_B_output_str = parse_test_results(A_B_output)
                        if k == max_iter:
                            with open('%s/%s'%(project_path, 'gpt_code_B_test_B'), 'w') as f:
                                f.write(output)
                            total_contents[i].append('gpt_code_B_test_B:%s'%output_str)

                            with open('%s/%s'%(project_path, 'gpt_code_A_test_B'), 'w') as f:
                                f.write(A_B_output)
                            total_contents[i].append('gpt_code_A_test_B:%s'%A_B_output_str)

                            if os.path.exists("%s/pom_backup.xml"%base_path):
                                os.system("cp %s/pom_backup.xml %s/pom.xml"%(base_path, base_path))
                            add_dependency_to_pom('%s/pom.xml'%base_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                            add_test_source_directory_to_pom('%s/pom.xml'%base_path, test_source_directory=gpt_path_B)
                            base_B_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(base_path, class_name_B))
                            base_B_output_str = parse_test_results(base_B_output)
                            total_contents[i].append('gpt_code_base_test_B:%s'%base_B_output_str)
                            with open('%s/%s'%(project_path, 'gpt_code_base_test_B'), 'w') as f:
                                f.write(base_B_output)
                            break

                        if 'SUCCESS' in output_str and 'SUCCESS' in A_B_output_str:
                            cur_same_prompt = same_prompt.format('B', 'B', 'B')
                            p.write('\n-----------------User(success but same)-----------------\n')
                            p.write(cur_same_prompt)
                            p.flush()
                            B_messages.append({"role": "user", "content": cur_same_prompt})
                            print('B Feedback (success but same) %s starting...'%k)
                            completion = client.chat.completions.create(
                                model="gpt-4-turbo",
                                # response_format={ "type": "json_object" },
                                temperature=temperature,
                                messages=B_messages
                            )
                            print('B Feedback %s end...'%k)
                            gpt_output = completion.choices[0].message.content
                            p.write('\n-----------------Assistant-----------------\n')
                            p.write(gpt_output)   
                            p.flush()
                            B_messages.append({"role": "assistant", "content": gpt_output})
                            gpt_output = extract_java_tags(gpt_output)
                            if len(gpt_output) > 0:
                                gpt_output = gpt_output[0]
                                # gpt_output = find_test_classes(gpt_output)
                                os.system('rm %s/%s.java'%(gpt_path_B, class_name_B))
                                test_B = gpt_output
                                class_name_B = extract_class_name(test_B)
                                # print(test_B)
                                test_B = '\n'.join(import_package_states) + '\n' + test_B
                                open('%s/%s.java'%(gpt_path_B, class_name_B), 'w').write(test_B)
                            else:
                                pass
                            B_feedback_thre += k + 1
                            k += 1
                            continue
                        else:
                            with open('%s/%s'%(project_path, 'gpt_code_B_test_B'), 'w') as f:
                                f.write(output)
                            total_contents[i].append('gpt_code_B_test_B:%s'%output_str)

                            with open('%s/%s'%(project_path, 'gpt_code_A_test_B'), 'w') as f:
                                f.write(A_B_output)
                            total_contents[i].append('gpt_code_A_test_B:%s'%A_B_output_str)

                            if os.path.exists("%s/pom_backup.xml"%base_path):
                                os.system("cp %s/pom_backup.xml %s/pom.xml"%(base_path, base_path))
                            add_dependency_to_pom('%s/pom.xml'%base_path, group_id="org.mockito", artifact_id="mockito-core", version="4.11.0", scope="test")
                            add_test_source_directory_to_pom('%s/pom.xml'%base_path, test_source_directory=gpt_path_B)
                            base_B_output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(base_path, class_name_B))
                            base_B_output_str = parse_test_results(base_B_output)
                            total_contents[i].append('gpt_code_base_test_B:%s'%base_B_output_str)
                            with open('%s/%s'%(project_path, 'gpt_code_base_test_B'), 'w') as f:
                                f.write(base_B_output)
                            break
                    error_msg = execute_command("echo '%s' | grep '\[ERROR\]' | grep -v 'Please refer to' | grep -v '\[Help 1\]' | grep -v '> \[Help 1\]' | grep -v 'To see the full stack trace' | grep -v 'Re-run Maven using the -X switch' | grep -v 'For more information about the errors'"%output)
                    error_prompt = "The test for version B has some bugs. Please repair the bugs and return the complete test method after repair. The requirements are the same to the previous. The names of the test classes are \"${{class_name}}TestV2\", \"$class_name\" is the name of the class under test. Please generate the tests using Junit4. Don't generate the package declaration statement. Please generate the import statements and the test class for version B and use ```java``` to surround the code. Don't use ```java``` to surround other things except the test class.\n\nError message:\n\n%s"%error_msg 
                    p.write('\n-----------------User-----------------\n')
                    p.write(error_prompt)
                    p.flush()
                    B_messages.append({"role": "user", "content": error_prompt})
                    print('B Feedback %s starting...'%k)
                    completion = client.chat.completions.create(
                        model="gpt-4-turbo",
                        # response_format={ "type": "json_object" },
                        temperature=temperature,
                        messages=B_messages
                    )
                    print('B Feedback %s end...'%k)
                    gpt_output = completion.choices[0].message.content
                    p.write('\n-----------------Assistant-----------------\n')
                    p.write(gpt_output)   
                    B_messages.append({"role": "assistant", "content": gpt_output})
                    gpt_output = extract_java_tags(gpt_output)
                    if len(gpt_output) > 0:
                        gpt_output = gpt_output[0]

                        # gpt_output = find_test_classes(gpt_output)
                        os.system('rm %s/%s.java'%(gpt_path_B, class_name_B))
                        test_B = gpt_output
                        class_name_B = extract_class_name(test_B)
                        test_B = '\n'.join(import_package_states) + '\n' + test_B
                        open('%s/%s.java'%(gpt_path_B, class_name_B), 'w').write(test_B)
                        p.flush()   
                    else:
                        pass
                    k += 1
            p.close()
            if whether_save == 'true':
                writer.writerow(total_contents[i])
                csv_f.flush()
        except:
            error_info = traceback.format_exc()
            open('%s/gpt_traceback'%(gpt_src), 'w').write(error_info)
            if whether_save == 'true':
                writer.writerow(total_contents[i])
                csv_f.flush()
    csv_f.close()
    os.system('cp %s/gpt.csv %s/final.csv'%(csv_path, csv_path))