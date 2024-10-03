import os,sys
print(os.getcwd())
sys.path.append(os.getcwd())

import gensim
from gensim import corpora
from gensim.models.ldamodel import LdaModel
from gensim.models.coherencemodel import CoherenceModel
import pyLDAvis.gensim_models as gensimvis
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from download_file.download_repomd import download_repo_metadata
from group.group_label import __repomd_get_group_file,get_groups_info,save_groups,merge_groups
from utils.json import load_file
from utils.logger import get_logger
import numpy as np
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

logger = get_logger(__name__)

# nltk.download('stopwords')
# nltk.download('punkt')
# nltk.download('punkt_tab')

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


def get_group_description(os_arch_ver,override=False):
    metas = load_file('./os_urls_total.json')
    all_description = {}
    for os_name,os_arch,os_ver in os_arch_ver:
        jsonkey = get_json_key(os_name,os_ver)
        for os_k,os_url in metas[jsonkey].items():
            os_path,os_files =download_repo_metadata(os_url.format(arch=os_arch, ver=os_ver), "./data/", override)
            if os_path==None:
                continue
            group_file = __repomd_get_group_file(os_path)
            if group_file:
                os_groups, os_cate, os_env, os_langp = get_groups_info(os.path.join(os_path, group_file).replace('\\', '/'))
                if os_groups ==None:
                    continue
                for key,item in os_groups.items():
                    if item["description"]=="" or len(item["description"])==0 or item["description"][0]=="":
                        continue
                    else:
                        all_description[key] = item["description"][0]
    description_list = list(all_description.values())
    return description_list

def preprocess(text):
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(text)
    filtered_words = [word for word in words if word not in stop_words and word not in ['.',',','?']]
    return filtered_words

def get_best_topic_num(description_list,topic_num_range):
    all_description = [preprocess(description) for description in description_list]
    dictionary = corpora.Dictionary(all_description)
    corpus = [dictionary.doc2bow(descri) for descri in all_description]
    coherence_values = []
    preplexity_values = []
    coherence_best_num_topics = None
    coherence_best_score = -1
    preplexity_best_num_topics = None
    preplexity_best_score = float('inf')
    for num_topic in topic_num_range:
        lda_model = LdaModel(corpus, num_topics=num_topic, id2word=dictionary, passes=15)
        coherence_model_lda = CoherenceModel(model=lda_model, texts=all_description, dictionary=dictionary, coherence='c_v')
        coherence_lda = coherence_model_lda.get_coherence()
        coherence_values.append(coherence_lda)
        if coherence_lda > coherence_best_score:
            coherence_best_score = coherence_lda
            coherence_best_num_topics = num_topic
        preplexity_lda = lda_model.log_perplexity(corpus)
        preplexity_values.append(preplexity_lda)
        if preplexity_lda < preplexity_best_score:
            preplexity_best_score = preplexity_lda
            preplexity_best_num_topics = num_topic
    return preplexity_values,coherence_values,preplexity_best_num_topics,coherence_best_num_topics,preplexity_best_score,coherence_best_score

def get_topic(description_list,topic_num):
    all_description = [preprocess(description) for description in description_list]
    dictionary = corpora.Dictionary(all_description)
    corpus = [dictionary.doc2bow(descri) for descri in all_description]
    lda_model = LdaModel(corpus, num_topics=topic_num, id2word=dictionary, passes=15)
    topics = lda_model.print_topics(num_words=50)
    for topic in topics:
        logger.info(f"topic:{topic}")

if __name__=="__main__":
    os_name_list = ["fedora","centos","openEuler","anolis","opencloudos"]
    os_versions = []
    os_arch = 'x86_64'
    for os_name in os_name_list:
        os_ver_list = get_ver_list(os_name)
        for os_ver in os_ver_list:
            os_versions.append((os_name,os_arch,os_ver))
    group_description_list = get_group_description(os_versions)
    # topic_num_range = range(2,20,1)
    # preplexity_values,coherence_values,prelexity_best_num_topics,coherence_best_num_topic,preplexity_best_score,coherence_best_score = get_best_topic_num(group_description_list,topic_num_range)
    # logger.info(f"preplexity_values:{preplexity_values}")
    # logger.info(f"coherence_values:{coherence_values}")
    # logger.info(f"prelexity_best_num_topics:{prelexity_best_num_topics}")
    # logger.info(f"coherence_best_num_topic:{coherence_best_num_topic}")
    # logger.info(f"preplexity_best_score:{preplexity_best_score}")
    # logger.info(f"coherence_best_score:{coherence_best_score}")
    get_topic(group_description_list,3)