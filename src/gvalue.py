import os,sys
print(os.getcwd())
sys.path.append(os.getcwd())

import os
import json
from utils.json import load_file
from utils.logger import get_logger
import numpy as np
from sentence_transformers import SentenceTransformer,util
from group.group_label import __repomd_get_group_file,get_groups_info,save_groups,merge_groups
from pkg.pkg import __repomd_get_primary_file,get_pkgs_info,save_pkgs,merge_pkgs
from download_file.download_repomd import download_repo_metadata

logger = get_logger(__name__)
    
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
        elif os_ver in [str(i) for i in range(21,28)]:
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

def name_simi_score(str1,str2):
    def edit_distance(s1, s2):
        m, n = len(s1), len(s2)
        dp = np.zeros((m+1, n+1))
        for i in range(m+1):
            for j in range(n+1):
                if i == 0:
                    dp[i][j] = j
                elif j == 0:
                    dp[i][j] = i
                elif s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j],      # 删除
                                       dp[i][j-1],      # 插入
                                       dp[i-1][j-1])   # 替换
        return dp[m][n]
    len_str1 = len(str1)
    len_str2 = len(str2)
    ed = edit_distance(str1, str2)
    max_len = max(len_str1, len_str2)
    similarity = 1 - (ed / max_len)
    return similarity

def weighted_jaccard_similarity(dict1,dict2):
    # 将字典的格式转换为集合格式
    set_1 = {(elem,eltype)for elem,eltype in dict1.items()}
    set_2 = {(elem,eltype)for elem,eltype in dict2.items()}
    # 类型到权重的映射
    type2weight = {"mandatory":1,"default":0.7,"conditional":0.4,"optional":0.1}
    intersection_weight = sum(min(type2weight[type_1],type2weight[type_2])
                       for (elem_1,type_1) in set_1
                       for (elem_2,type_2) in set_2
                       if elem_1 == elem_2)
    union_dict = {}
    for elem,eltype in set_1:
        union_dict[elem] = type2weight[eltype]
    for elem,eltype in set_2:
        if elem in union_dict:
            union_dict[elem] = max(union_dict[elem], type2weight[eltype])
        else:
            union_dict[elem] = type2weight[eltype]
    union_weight = sum(union_dict.values())
    similarity = intersection_weight / union_weight if union_weight else 0
    return similarity

def get_compact_value(all_groups,all_pkgs,model):
    compact_result = []
    for group,info in all_groups.items():
        sum = 0
        count = 0
        compact_value = 0
        simi_pkgs = []
        group_descr = info["description"][0]
        pkg_name_list = info["packagelist"]
        pkg_desc_list = []
        new_pkg_name_list = []
        new_pkg_list = []
        for name in pkg_name_list:
            if name not in all_pkgs:
                logger.info("Below pkgs are not found in primary")
                logger.info(name)
                continue
            else:
                pkg_desc_list.append(all_pkgs[name]["description"])
                new_pkg_name_list.append(name)
                new_pkg_list[name] = all_pkgs[name]["description"]
        embeddings = model.encode(pkg_desc_list,convert_to_tensor=True)
        cosine_score = util.cos_sim(embeddings,embeddings)
        cosine_score = cosine_score.cpu().detach().numpy()
        for i in range(cosine_score.shape[0]):
            for j in range(cosine_score.shape[1]):
                item = {
                    "pkg1":new_pkg_name_list[i],
                    "pkg2":new_pkg_name_list[j],
                    "score":cosine_score[i][j]
                }
                simi_pkgs.append(item)
                sum += cosine_score[i][j]
                count +=1
        compact_value = sum / count
        compact_result.append(
            {
                "group_name":group,
                "compact_score":compact_value,
                "description":group_descr,
                "pkgs":new_pkg_list,
                "simi":simi_pkgs
            }
        )
    return compact_result

def write_json(data,path):
    with open(path,'w') as f:
        json.dump(data,f,indent=4)

def get_relevance_value(all_groups,all_pkgs,model):
    relevance_result = []
    for group,info in all_groups.items():
        group_desc = [info["description"][0]]
        pkg_desc_list = []
        pkg_name_list = info["packagelist"]
        new_pkg_name_list = []
        for name in pkg_name_list:
            if name in all_pkgs:
                new_pkg_name_list.append(name)
                pkg_desc_list.append(all_pkgs[name]["description"])
        group_embed = model.encode(group_desc,convert_to_tensor=True)
        pkg_embed = model.encode(pkg_desc_list,convert_to_tensor=True)
        cosine_score = util.cos_sim(group_embed,pkg_embed)
        cosine_score = cosine_score.cpu().detach().numpy()
        sum = 0
        count = 0
        for i in range(cosine_score.shape[1]):
            sum += cosine_score[0][i]
            count +=1
        relevance_score = sum / count
        relevance_result.append(
            {
                "group_name":group,
                "relevance_score": relevance_score,
                "description":group_desc,
                "pkgs":new_pkg_name_list,
            }
        )
    return relevance_result

def get_difference_value(all_groups,model):
    difference_result = []
    all_group_desc = [info["description"][0] for group,info in all_groups.items()]
    all_group_name = [info["name"][0] for group,info in all_groups.items()]
    all_group_pkglist = [info["packagelist"] for group,info in all_groups.items()]
    group_desc_embed = model.encode(all_group_desc,convert_to_tensor=True)
    desc_cosine_socre = util.cos_sim(group_desc_embed,group_desc_embed)
    desc_cosine_simi = desc_cosine_socre.cpu().detach().numpy()
    name_edit_simi = [] 
    for i,g1 in enumerate(all_group_name):
        row = []
        for j,g2 in enumerate(all_group_name):
            similarity = name_simi_score(g1, g2)
            row.append(similarity)
        name_edit_simi.append(similarity)
    pl_jaccard_simi = []
    for i, pl1 in enumerate(all_group_pkglist):
        row = []
        for j,pl2 in enumerate(all_group_pkglist):
            similarity = weighted_jaccard_similarity(pl1,pl2)
            row.append(similarity)
        pl_jaccard_simi.append(row)
    for i in range(desc_cosine_simi.shpae[0]):
        total_diff = 0
        for j in range(desc_cosine_simi.shape[1]):
            if i==j:
                continue
            desc_diff = 1 - (desc_cosine_simi[i][j]+ 1)/2 
            name_diff = name_edit_simi[i][j]
            pl_diff = 1- pl_jaccard_simi[i][j]
            diff_item = (desc_diff + name_diff + pl_diff) /3
            total_diff += diff_item
        difference_score = total_diff / (desc_cosine_simi.shape[1] - 1)
        difference_result.append(
            {
                "group_name":all_group_name[i],
                "difference_score": difference_score,
                "description":all_group_desc[i],
                "pkgs":all_group_pkglist[i],
            }
        )
    return difference_result

def get_distribution_value(all_groups):
    pkg_num_in_group = count_pkgnum_eachgroup(all_groups)
    pass

def count_pkgnum_eachgroup(all_groups):
    pkg_group = {}
    for item in all_groups.values():
        pkg_num = len(item['packagelist'])
        if pkg_num in pkg_group:
            pkg_group[pkg_num] +=1
        else:
            pkg_group[pkg_num] = 1
    pkg_group_sorted = dict(sorted(pkg_group.items()))
    logger.info(pkg_group_sorted)
    return pkg_group_sorted 

def get_total_value(compact_list,relevance_list,difference_list,distribution_list):
    total_value = []
    for i,item in enumerate(compact_list):
        group_name = item["group_name"]
        compact_score = item["compact_score"]
        relevance_score = relevance_list[i]["relevance_score"]
        difference_score = difference_list[i]["difference_score"]
        total_score = (compact_score + relevance_score + difference_score) / 3
        total_value.append(
            {
                "group_name":group_name,
                "total_score":total_score,
                "compact_score":compact_score,
                "relevance_score":relevance_score,
                "difference_score": difference_score
            }
        )
    return total_value

def get_group_value(os_arch_ver,model,override=False):
    metas = load_file('./os_urls_total.json')
    for os_name,os_arch,os_ver in os_arch_ver:
        logger.info(f"going on {os_name}_{os_arch}_{os_ver}")
        jsonkey = get_json_key(os_name,os_ver)
        all_groups = None
        all_pkgs = None
        for os_k,os_url in metas[jsonkey].items():
            os_path,os_files =download_repo_metadata(os_url.format(arch=os_arch, ver=os_ver), "./data/", override)
            group_file = __repomd_get_group_file(os_path)
            primary_file = __repomd_get_primary_file(os_path)
            if group_file:
                os_groups, os_cate, os_env, os_langp = get_groups_info(os.path.join(os_path, group_file).replace('\\', '/'))
                all_groups = merge_groups(all_groups,os_groups)
            if primary_file:
                os_pkgs = get_pkgs_info(os.path.join(os_path, primary_file).replace('\\', '/'))
                all_pkgs = merge_pkgs(all_pkgs,os_pkgs)
        compact_value = get_compact_value(all_groups,all_pkgs,model)
        result_dir = f"./result/gvalue/{os_name}"
        if not os.path.exists(result_dir):
            os.mkdir(result_dir)
        compact_value_path = os.path.join(result_dir,"compact.json")
        write_json(compact_value,compact_value_path)
        relevance_value = get_relevance_value(all_groups,all_pkgs,model)
        relevance_value_path = os.path.join(result_dir,"relevance.json")
        write_json(relevance_value,relevance_value_path)
        difference_value = get_difference_value(all_groups,model)
        difference_value_path = os.path.join(result_dir,"difference.json")
        write_json(difference_value,difference_value_path)
        distribution_value = get_distribution_value(all_groups)
        # distribution_value_path = os.path.join(result_dir,"distribution.json")
        # write_json(distribution_value,distribution_value_path)
        total_value = get_total_value(compact_value,relevance_value,difference_value,distribution_value)
        total_value_path = os.path.join(result_dir,"total.json")
        write_json(total_value,total_value_path)

if __name__=="__main__":
    os_versions = [
        ("fedora", "x86_64", "40"),
        ('centos', 'x86_64', '7'),
        ("openEuler", "x86_64", "openEuler-23.09")
        ("anolis", "x86_64", "8.9"),
        ("openCloudOS", "x86_64", "9.2"),
    ]
    model = SentenceTransformer("all-MiniLM-L6-v2",device="cuda:5")
    get_group_value(os_versions,model,False)