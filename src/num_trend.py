import os,sys
print(os.getcwd())
sys.path.append(os.getcwd())

from group.group_label import __repomd_get_group_file,get_groups_info,save_groups,merge_groups
from pkg.pkg import __repomd_get_primary_file,get_pkgs_info,save_pkgs,merge_pkgs
from download_file.download_repomd import download_repo_metadata

import os
import json
from utils.json import load_file
from utils.logger import get_logger

logger = get_logger(__name__)

def get_ver_list(os_name):
    if os_name=="centos":
        os_ver_list = ['3.7','3.8','3.9']
        for major in range(4,7):
            if major==5:
                major_end = 11
            elif major==6:
                major_end = 9
            else:
                major_end = 9
            for minor in range(0,major_end+1):
                os_ver_list.append(f"{major}.{minor}")
        other_ver = ['7','8']
        # other_ver = ['7','7.0.1406','7.1.1503','7.2.1511','7.3.1611','7.4.1708','7.5.1804','7.6.1810','7.7.1908','7.8.2003','7.9.2009','8','8-stream','8.0.1905','8.1.1911','8.2.2004','8.3.2011','8.4.2105','8.5.2111']
        os_ver_list.extend(other_ver)
        return os_ver_list
    elif os_name == "fedora":
        os_ver_list = [str(i) for i in range(7,40)]
        return os_ver_list
    elif os_name == "openEuler":
        os_ver_list = ["openEuler-20.03-LTS","openEuler-20.09","openEuler-21.03","openEuler-21.09","openEuler-22.03-LTS","openEuler-22.09","openEuler-23.03","openEuler-23.09"]
        return os_ver_list
    elif os_name == "anolis":
        os_ver_list = ["7.7","7.9","8","8.2","8.4","8.6","8.8","8.9"]
        return os_ver_list
    elif os_name == "opencloudos":
        os_ver_list = ["7","8","8.5","8.6","8.8","9","9.0"]
        return os_ver_list
    
def get_json_key(os_name,os_ver):
    if os_name=="fedora":
        """
        37,38,39 --> fedora1
        28-36 --> fedora 2
        21-27 --> fedora 3
        7-20 fedora 4
        """
        if os_ver in ['37','38','39']:
            jsonkey = 'fedora1'
        elif os_ver in [str(i) for i in range(28,37)]:
            jsonkey = 'fedora2'
        elif os_ver in [str(i) for i in range(28,37)]:
            jsonkey = 'fedora2'
        elif os_ver in [str(i) for i in range(21,38)]:
            jsonkey = 'fedora3'
        elif os_ver in [str(i) for i in range(7,21)]:
            jsonkey = 'fedora4'
        return jsonkey
    elif os_name=="centos":
        if float(os_ver)<=5.1:
            jsonkey = 'centos1'
        elif float(os_ver)<= 6.6:
            jsonkey = 'centos2'
        elif os_ver == "7" or os_ver == "8":
            jsonkey = 'centos4'
        else:
            jsonkey = 'centos3'
        return jsonkey
    elif os_name=="openEuler":
        if os_ver in ["openEuler-20.03-LTS","openEuler-22.03-LTS","openEuler-23.03","openEuler-23.09"]:
            jsonkey = "openEuler1"
        else:
            jsonkey = "openEuler2"
        return jsonkey
    elif os_name=="anolis":
        # todo ver 23,23.0 and 23.1
        if os_ver in ['7.7','7.9']:
            jsonkey = "anolis1"
        elif os_ver in ['8','8.2','8.4','8.6','8.8','8.9']:
            jsonkey = "anolis2"
        return jsonkey
    elif os_name=="opencloudos":
        if os_ver in ['8','8.8']:
            jsonkey = "openCloudOS1"
        elif os_ver in ['8.5']:
            jsonkey = "openCloudOS2"
        elif os_ver in ['8.6']:
            jsonkey = "openCloudOS3"
        elif os_ver in ['9','9.0']:
            jsonkey = "openCloudOS4"
        elif os_ver in ['7']:
            jsonkey = "openCloudOS5"
        return jsonkey

def get_pkg2group(all_groups):
    pkg2group = {}
    if all_groups == None:
        return pkg2group
    for item in all_groups.values():
        group = ".".join(item["name"])
        for pkg,pkg_opt in item["packagelist"].items():
            if pkg in pkg2group:
                if group not in pkg2group[pkg]:
                    pkg2group[pkg][group] = pkg_opt
                else:
                    continue
            else:
                pkg2group[pkg] = {group:pkg_opt}
    return pkg2group

def write_json(data,path):
    with open(path,'w') as f:
        json.dump(data,f,indent=4)

def count_pkg_in_group(all_groups):
    pkg2group = get_pkg2group(all_groups)
    return len(pkg2group)

def get_number_trend(os_arch_ver,override=False):
    metas = load_file('./os_urls_total.json')
    group_counts_res = {
        "x86_64":[],
        "aarch64":[]
    }
    inpkg_counts_res = {
        "x86_64":[],
        "aarch64":[]
    }
    tolpkg_counts_res = {
        "x86_64":[],
        "aarch64":[]
    }
    for os_name,os_arch,os_ver in os_arch_ver:
        logger.info(f"going on {os_name}_{os_arch}_{os_ver}")
        all_groups = None
        all_pkgs = None
        result_dir = f"./result/num_trend/{os_name}"
        if not os.path.exists(result_dir):
            os.mkdir(result_dir)
        group_path = f"./format/group/eachOS/{os_name}_{os_arch}_{os_ver}"
        pkgs_path = f"./format/pkg/eachOS/{os_name}_{os_arch}_{os_ver}"
        jsonkey = get_json_key(os_name,os_ver)
        for os_k,os_url in metas[jsonkey].items():
            os_path,os_files =download_repo_metadata(os_url.format(arch=os_arch, ver=os_ver), "./data/", override)
            if os_path==None:
                continue
            group_file = __repomd_get_group_file(os_path)
            primary_file = __repomd_get_primary_file(os_path)
            if group_file:
                os_groups, os_cate, os_env, os_langp = get_groups_info(os.path.join(os_path, group_file).replace('\\', '/'))
                save_groups(os_groups,group_path,os_k)
                all_groups = merge_groups(all_groups,os_groups)
            if primary_file:
                os_pkgs = get_pkgs_info(os.path.join(os_path, primary_file).replace('\\', '/'))
                save_pkgs(os_pkgs,pkgs_path,os_k)
                all_pkgs = merge_pkgs(all_pkgs,os_pkgs)
        save_groups(all_groups,group_path,"total")
        save_pkgs(all_pkgs,pkgs_path,"total")
        group_count = len(all_groups) if not (all_groups is None) else 0
        inpkg_count = count_pkg_in_group(all_groups) if not (all_groups is None) else 0
        pkg_count = len(all_pkgs)
        group_counts_res[os_arch].append({"ver":os_ver,"num":group_count})
        inpkg_counts_res[os_arch].append({"ver":os_ver,"num":inpkg_count})
        tolpkg_counts_res[os_arch].append({"ver":os_ver,"num":pkg_count})
        logger.info(f"{os_ver}_{os_arch}:g-{group_count},inpkg-{inpkg_count},tolpkg-{pkg_count}")
    group_counts_path = os.path.join(result_dir,"group.json")
    inpkg_counts_path = os.path.join(result_dir,"inpkg.json")
    tolpkg_counts_path = os.path.join(result_dir,"tolpkg.json")
    write_json(group_counts_res,group_counts_path)
    write_json(inpkg_counts_res,inpkg_counts_path)
    write_json(tolpkg_counts_res,tolpkg_counts_path)

if __name__=="__main__":
    os_name = "fedora" #
    os_arch_list = ['x86_64']
    os_ver_list = get_ver_list(os_name)
    os_versions = []
    for os_arch in os_arch_list:
        for os_ver in os_ver_list:
            os_versions.append((os_name,os_arch,os_ver))
    get_number_trend(os_versions,False)