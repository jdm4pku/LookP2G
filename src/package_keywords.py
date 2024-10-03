import os,sys
print(os.getcwd())
sys.path.append(os.getcwd())

from download_file.download_repomd import download_repo_metadata
from group.group_label import __repomd_get_group_file,get_groups_info,save_groups,merge_groups
from pkg.pkg import __repomd_get_primary_file,get_pkgs_info,save_pkgs,merge_pkgs
from sklearn.feature_extraction.text import TfidfVectorizer
from utils.json import load_file
from utils.logger import get_logger
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

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

def get_package_description(os_arch_ver,override=False):
    metas = load_file('./os_urls_total.json')
    pkg_desc_in_group = {}
    pkg_desc_not_in_group = {}
    for os_name,os_arch,os_ver in os_arch_ver:
        logger.info(f"going on {os_name}_{os_arch}_{os_arch}")
        all_groups = None
        all_pkgs = None
        jsonkey = get_json_key(os_name,os_ver)
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
        pkg_in_group = []
        if all_groups==None:
            all_groups = {}
        for group, info in all_groups.items():
            for pkg in info["packagelist"]:
                pkg_in_group.append(pkg)
        for pkg, info in all_pkgs.items():
            if pkg in pkg_in_group: ## 组内的软件包
                if info["description"] is not None:
                    pkg_desc_in_group[pkg] = info["description"]
            else: ## 组外的软件包
                if info["description"] is not None:
                    pkg_desc_not_in_group[pkg] = info["description"]
    pkg_desc_in_group_list = list(pkg_desc_in_group.values())
    pkg_desc_not_in_group_list = list(pkg_desc_not_in_group.values())
    return pkg_desc_in_group_list,pkg_desc_not_in_group_list

def preprocess_text(desc_pkg):
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(desc_pkg)
    filtered_words = [word for word in words if word not in stop_words and word not in ['.',',','?']]
    return ' '.join(filtered_words)

def get_key_words(des_pkg_list,top_n=50):
    processed_desc = [preprocess_text(desc) for desc in des_pkg_list]
    tfidf_vectorizer = TfidfVectorizer(max_features=top_n)
    tfidf_matrix = tfidf_vectorizer.fit_transform(processed_desc)
    feature_names = tfidf_vectorizer.get_feature_names_out()
    return feature_names

if __name__=="__main__":
    os_name_list = ["fedora","centos","openEuler","anolis","opencloudos"]
    os_versions = []
    os_arch = 'x86_64'
    for os_name in os_name_list:
        os_ver_list = get_ver_list(os_name)
        for os_ver in os_ver_list:
            os_versions.append((os_name,os_arch,os_ver))
    package_descrip_in_group,pacakge_descrip_not_in_group = get_package_description(os_versions, False)
    key_words_num = 50
    key_words_in_group = get_key_words(package_descrip_in_group,key_words_num)
    key_words_not_in_group = get_key_words(pacakge_descrip_not_in_group,key_words_num)
    logger.info(f"key words of packages in group:{key_words_in_group}")
    logger.info(f"key owrds of packages not in group:{key_words_not_in_group}")


