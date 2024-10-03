import os,sys
print(os.getcwd())
sys.path.append(os.getcwd())

import json
from utils.json import load_file
from utils.logger import get_logger
from group.group_label import __repomd_get_group_file,get_groups_info,save_groups,merge_groups
from pkg.pkg import __repomd_get_primary_file,get_pkgs_info,save_pkgs,merge_pkgs
from download_file.download_repomd import download_repo_metadata

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
        other_ver = ['7'] #'8'
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
        os_ver_list = ["7","8","8.5","8.6","8.8","8.10","9","9.0","9.2"]
        return os_ver_list

def get_json_key(os_name,os_ver):
    if os_name=="fedora":
        """
        39,40 --> fedora0
        37,38 --> fedora1
        28-36 --> fedora 2
        21-27 --> fedora 3
        7-20 fedora 4
        """
        if os_ver in ['39','40']:
            jsonkey = 'fedora0'
        elif os_ver in ['37','38']:
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
        if os_ver in ['8','8.8','8.10']:
            jsonkey = "openCloudOS1"
        elif os_ver in ['8.5']:
            jsonkey = "openCloudOS2"
        elif os_ver in ['8.6']:
            jsonkey = "openCloudOS3"
        elif os_ver in ['9','9.0','9.2']:
            jsonkey = "openCloudOS4"
        elif os_ver in ['7']:
            jsonkey = "openCloudOS5"
        return jsonkey
    
def get_in_pkg(all_groups):
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

def compute_change_in_pkg(pre_in_pkg,all_in_pkg):
    add_in_pkg = []
    delete_in_pkg = []
    if pre_in_pkg == None:
        delete_in_pkg = []
        for key, value in all_in_pkg.items():
            add_in_pkg.append(
                {
                    "pkg":key,
                    "group":list(value.keys())[0]
                }
            )
        return add_in_pkg,delete_in_pkg
    if all_in_pkg == None:
        add_in_pkg = []
        for key,value in pre_in_pkg.items():
            delete_in_pkg.append(
                {
                    "pkg":key,
                    "group":list(value.keys())[0]
                }
            )
        return add_in_pkg,delete_in_pkg
    for key,value in all_in_pkg.items():
        if key not in pre_in_pkg:
            add_in_pkg.append(
                {
                    "pkg":key,
                    "group":list(value.keys())[0]
                }
            )
    for key,value in pre_in_pkg.items():
        if key not in all_in_pkg:
            delete_in_pkg.append(
                {
                    "pkg":key,
                    "group":list(value.keys())[0]
                }
            )
    return add_in_pkg,delete_in_pkg

def write_json(data,path):
    with open(path,'w') as f:
        json.dump(data,f,indent=4)

def get_inpkg_flow(os_arch_ver,override=False):
    metas = load_file('./os_urls_total.json')
    add_inpkg_list = []
    remove_inpkg_list = []
    pkg_list = []
    add_compare_pkg_list = []
    remove_compare_pkg_list = []
    first_in_pkg_ver = True
    pre_inpkg = None
    add_inpkg_flow = {
        "from_totalpkg": 0,
        "from_external":0
    }
    remove_inpkg_flow = {
        "to_totalpkg":0,
        "to_external":0
    }
    for os_name,os_arch,os_ver in os_arch_ver:
        logger.info(f"going on {os_name}_{os_arch}_{os_ver}")
        all_groups = None
        all_pkgs = None
        jsonkey = get_json_key(os_name,os_ver)
        # 计算当前版本所有的组内软件包
        for os_k,os_url in metas[jsonkey].items():
            os_path,os_files =download_repo_metadata(os_url.format(arch=os_arch, ver=os_ver), "./data/", override)
            if os_path==None:
                continue
            group_file = __repomd_get_group_file(os_path)
            primary_file = __repomd_get_primary_file(os_path)
            if group_file:
                os_groups, os_cate, os_env, os_langp = get_groups_info(os.path.join(os_path, group_file).replace('\\', '/'))
                all_groups = merge_groups(all_groups,os_groups)
            if primary_file:
                os_pkgs = get_pkgs_info(os.path.join(os_path, primary_file).replace('\\', '/'))
                all_pkgs = merge_pkgs(all_pkgs,os_pkgs)
        ## inpkg内容变更
        all_in_pkg = get_in_pkg(all_groups)
        if pre_inpkg==None and first_in_pkg_ver==True:
            pre_inpkg = all_in_pkg
            first_in_pkg_ver = False
        else:
            add_in_pkg,delete_in_pkg = compute_change_in_pkg(pre_inpkg,all_in_pkg)
            add_inpkg_list.append(add_in_pkg)
            remove_inpkg_list.append(delete_in_pkg)
            pre_inpkg = all_in_pkg
        pkg_list.append(all_pkgs) ## 所有版本的软件包
    add_compare_pkg_list = pkg_list[:-1]
    remove_compare_pkg_list = pkg_list[1:]
    assert len(add_inpkg_list) == len(add_compare_pkg_list)
    assert len(remove_inpkg_list) == len(remove_compare_pkg_list)
    logger.info(f"going on inpkg add flow")
    version_detail_results = {}
    for i in range(len(add_inpkg_list)): # 增加 #可以细化观察一下不同版本之间的流向
        version_add_inpkg_flow = {
            "from_totalpkg": 0,
            "from_external":0
        }
        os_name,os_arch,os_ver = os_arch_ver[i+1]
        logger.info(f"going on {os_name}_{os_arch}_{os_ver}")
        inpkg_list = add_inpkg_list[i]
        prepkg_list = add_compare_pkg_list[i]
        for inpkg in inpkg_list:
            inpkg_name = inpkg["pkg"]
            if inpkg_name in prepkg_list:
                add_inpkg_flow["from_totalpkg"] +=1
                version_add_inpkg_flow["from_totalpkg"] +=1
            else:
                add_inpkg_flow["from_external"] +=1
                version_add_inpkg_flow["from_external"] +=1
        version_detail_results[os_ver] = {
            "add":version_add_inpkg_flow
        }
    logger.info(f"from_totalpkg:{add_inpkg_flow['from_totalpkg']}, from_external:{add_inpkg_flow['from_external']}")
    logger.info(f"going on inpkg remove flow")
    for i in range(len(remove_inpkg_list)): # 减少
        version_remove_inpkg_flow = {
            "to_totalpkg":0,
            "to_external":0
        }
        os_name,os_arch,os_ver = os_arch_ver[i+1]
        logger.info(f"going on {os_name}_{os_arch}_{os_ver}")
        inpkg_list = remove_inpkg_list[i]
        curpkg_list = remove_compare_pkg_list[i]
        for inpkg in inpkg_list:
            inpkg_name = inpkg["pkg"]
            if inpkg_name in curpkg_list:
                remove_inpkg_flow["to_totalpkg"] +=1
                version_remove_inpkg_flow["to_totalpkg"] +=1
            else:
                remove_inpkg_flow["to_external"] +=1
                version_remove_inpkg_flow["to_external"] +=1
        version_detail_results[os_ver]["remove"] = version_remove_inpkg_flow
    logger.info(f"to_totalpkg:{remove_inpkg_flow['to_totalpkg']}, to_external:{remove_inpkg_flow['to_external']}")
    result_dir = f"./result/inpkg_flow/{os_name}"
    if not os.path.exists(result_dir):
        os.mkdir(result_dir)
    flow_result = {
        "add":add_inpkg_flow,
        "remove":remove_inpkg_flow
    }
    detail_flow_result_path = os.path.join(result_dir,"flow_detailed.json")
    flow_result_path = os.path.join(result_dir,"flow.json")
    write_json(flow_result,flow_result_path)
    write_json(version_detail_results,detail_flow_result_path)
  
if __name__=="__main__":
    os_name = "fedora"
    os_arch_list = ['x86_64']
    os_ver_list = get_ver_list(os_name)
    os_versions = []
    for os_arch in os_arch_list:
        for os_ver in os_ver_list:
            os_versions.append((os_name,os_arch,os_ver))
    get_inpkg_flow(os_versions,False)

