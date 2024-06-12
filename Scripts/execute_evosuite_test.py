import os
import csv
import subprocess
import re
import sys
import xml.etree.ElementTree as ET
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
def execute_command(cmd):
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout
    error_output = result.stderr
    return output + ";ERROR:%s"%error_output
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

# Example usage

input_file = 'evosuite.csv'
consider_hash = 'none'
prefix = input_file.split('.')[0]
total_contents_csv = csv.reader(open(input_file, 'r', newline=''))
total_contents = []
for row in total_contents_csv:
    total_contents.append(row)

a_generate_true = "generate A TRUE"
b_generate_true = "generate B TRUE"


output_dir = "./merge"
output_file = '%s/evosuite_test.csv'%(output_dir)
already_contents = []
if os.path.exists(output_file):
    already_contents_csv = csv.reader(open(output_file, 'r', newline=''))
    for row in already_contents_csv:
        already_contents.append(row)




for i, each in enumerate(total_contents):
    project_name = each[1]
    commit_hash = each[2]
    short_commit_hash = commit_hash[:7]
    file_name = each[3]
    cur_strategy = each[4]
    java_version = each[7]
    class_path = re.search(r'src/main/java/(.*)', file_name).group(1)[:-5]
    gen_test_path = class_path.replace('/', '.')
    gen_test_path = "%s_ESTest"%gen_test_path
    version_base="%s-base"%(project_name)
    version_middle_A="%s-middle-A"%project_name
    version_middle_B="%s-middle-B"%project_name
    version_M="%s-M"%project_name
    version_R="%s-R"%project_name

    overall_dir="./merge/projects"

    if consider_hash != 'none' and commit_hash != consider_hash:
        total_contents[i] = already_contents[i]
        continue
    elif consider_hash != 'none' and commit_hash == consider_hash:
        pass
    elif consider_hash == 'none':
        pass

    module_name = re.search(r'(.*)/src/main/java', file_name)
    path = '%s/%s-%s' % (overall_dir, project_name, short_commit_hash)
    
    evosuite_path_A = '%s/%s/%s' % (path, version_middle_A, 'evosuite_tests')
    evosuite_path_B = '%s/%s/%s' % (path, version_middle_B, 'evosuite_tests')

    if module_name:
        module_name = module_name.group(1)

        A_path = '%s/%s/%s' % (path, version_middle_A, module_name)
        B_path = '%s/%s/%s' % (path, version_middle_B, module_name)

    else:
        A_path = '%s/%s' % (path, version_middle_A)
        B_path = '%s/%s' % (path, version_middle_B)

    PATH = os.environ.get('PATH')
    JAVA = os.environ.get(java_version)
    os.environ['PATH'] = '%s:%s'%(JAVA, PATH)
    

    if not os.path.exists("%s/pom_backup.xml"%A_path):
        os.system("cp %s/pom.xml %s/pom_backup.xml"%(A_path, A_path))
    if not os.path.exists("%s/pom_backup.xml"%B_path):
        os.system("cp %s/pom.xml %s/pom_backup.xml"%(B_path, B_path))



    if a_generate_true in each:
        if os.path.exists("%s/pom_backup.xml"%A_path):
            os.system("cp %s/pom_backup.xml %s/pom.xml"%(A_path, A_path))
        add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.evosuite", artifact_id="evosuite-standalone-runtime", version="1.0.6", scope="test")
        add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.hamcrest", artifact_id="hamcrest-core", version="1.3", scope="test")
        add_test_source_directory_to_pom('%s/pom.xml'%A_path, test_source_directory=evosuite_path_A)
        # execute_command("mvn clean compile --file %s/pom.xml"%(A_path))        
        output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(A_path, gen_test_path))        
        with open('%s/%s'%(path, 'gen_code_A_test_A'), 'w') as f:
            f.write(output)
        output_str = parse_test_results(output)
        total_contents[i].append('gen_code_A_test_A:%s'%output_str)
        print('gen_code_A_test_A:%s'%output_str)


        if os.path.exists("%s/pom_backup.xml"%B_path):
            os.system("cp %s/pom_backup.xml %s/pom.xml"%(B_path, B_path))

        add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.evosuite", artifact_id="evosuite-standalone-runtime", version="1.0.6", scope="test")
        add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.hamcrest", artifact_id="hamcrest-core", version="1.3", scope="test")
        add_test_source_directory_to_pom('%s/pom.xml'%B_path, test_source_directory=evosuite_path_A)
        # print("mvn test --file %s/pom.xml -Dtest=%s"%(B_path, gen_test_path))
        # execute_command("mvn clean compile --file %s/pom.xml"%(B_path))
        output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(B_path, gen_test_path))
        with open('%s/%s'%(path, 'gen_code_B_test_A'), 'w') as f:
            f.write(output)
        output_str = parse_test_results(output)
        total_contents[i].append('gen_code_B_test_A:%s'%output_str)
        print('gen_code_B_test_A:%s'%output_str)
    if b_generate_true in each:
        if os.path.exists("%s/pom_backup.xml"%A_path):
            os.system("cp %s/pom_backup.xml %s/pom.xml"%(A_path, A_path))

        add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.evosuite", artifact_id="evosuite-standalone-runtime", version="1.0.6", scope="test")
        add_dependency_to_pom('%s/pom.xml'%A_path, group_id="org.hamcrest", artifact_id="hamcrest-core", version="1.3", scope="test")
        add_test_source_directory_to_pom('%s/pom.xml'%A_path, test_source_directory=evosuite_path_B)
        # execute_command("mvn clean compile --file %s/pom.xml "%(A_path))        
        output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(A_path, gen_test_path))        
        with open('%s/%s'%(path, 'gen_code_A_test_B'), 'w') as f:
            f.write(output)
        output_str = parse_test_results(output)
        total_contents[i].append('gen_code_A_test_B:%s'%output_str)
        print('gen_code_A_test_B:%s'%output_str)

        if os.path.exists("%s/pom_backup.xml"%B_path):
            os.system("cp %s/pom_backup.xml %s/pom.xml"%(B_path, B_path))
        add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.evosuite", artifact_id="evosuite-standalone-runtime", version="1.0.6", scope="test")
        add_dependency_to_pom('%s/pom.xml'%B_path, group_id="org.hamcrest", artifact_id="hamcrest-core", version="1.3", scope="test")
        add_test_source_directory_to_pom('%s/pom.xml'%B_path, test_source_directory=evosuite_path_B)
        # execute_command("mvn clean compile --file %s/pom.xml "%(B_path))
        output = execute_command("mvn clean test --file %s/pom.xml -Dtest=%s"%(B_path, gen_test_path))
        with open('%s/%s'%(path, 'gen_code_B_test_B'), 'w') as f:
            f.write(output)
        output_str = parse_test_results(output)
        total_contents[i].append('gen_code_B_test_B:%s'%output_str)
        print('gen_code_B_test_B:%s'%output_str)
writer = csv.writer(open('%s/%s_run.csv'%(output_dir, prefix), 'w', newline=''))
writer.writerows(total_contents)