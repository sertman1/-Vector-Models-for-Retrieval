import itertools
import re
from collections import Counter, defaultdict
from typing import Dict, List, NamedTuple

import numpy as np
from numpy.linalg import norm
from nltk.stem.snowball import SnowballStemmer
from nltk.tokenize import word_tokenize

### File IO and processing

class Document(NamedTuple):
    doc_id: int
    author: List[str]
    title: List[str]
    keyword: List[str]
    abstract: List[str]

    def sections(self):
        return [self.author, self.title, self.keyword, self.abstract]

    def __repr__(self):
        return ( + f"author: {self.author}\n" +
            f"  title: {self.title}\n" +
            f"  keyword: {self.keyword}\n" +
            f"  abstract: {self.abstract}")

def read_stopwords(file):
    with open(file) as f:
        return set([x.strip() for x in f.readlines()])

stopwords = read_stopwords('common_words')

stemmer = SnowballStemmer('english')

def read_docs(file):
    '''
    Reads the corpus into a list of Documents
    '''
    docs = [defaultdict(list)]  # empty 0 index
    category = ''
    with open(file) as f:
        i = 0
        for line in f:
            line = line.strip()
            if line.startswith('.I'):
                i = int(line[3:])
                docs.append(defaultdict(list))
            elif re.match(r'\.\w', line):
                category = line[1]
            elif line != '':
                for word in word_tokenize(line):
                    docs[i][category].append(word.lower())

    return [Document(i + 1, d['A'], d['T'], d['K'], d['W'])
        for i, d in enumerate(docs[1:])]

def stem_doc(doc: Document):
    return Document(doc.doc_id, *[[stemmer.stem(word) for word in sec]
        for sec in doc.sections()])

def stem_docs(docs: List[Document]):
    return [stem_doc(doc) for doc in docs]

def remove_stopwords_doc(doc: Document):
    return Document(doc.doc_id, *[[word for word in sec if word not in stopwords]
        for sec in doc.sections()])

def remove_stopwords(docs: List[Document]):
    return [remove_stopwords_doc(doc) for doc in docs]



### Term-Document Matrix

class TermWeights(NamedTuple):
    author: float
    title: float
    keyword: float
    abstract: float

def compute_doc_freqs(docs: List[Document]):
    '''
    Computes document frequency, i.e. how many documents contain a specific word
    '''
    freq = Counter()
    for doc in docs:
        words = set()
        for sec in doc.sections():
            for word in sec:
                words.add(word)
        for word in words:
            freq[word] += 1
    return freq

def compute_tf(doc: Document, doc_freqs: Dict[str, int], weights: list):
    vec = defaultdict(float)
    for word in doc.author:
        vec[word] += weights.author
    for word in doc.keyword:
        vec[word] += weights.keyword
    for word in doc.title:
        vec[word] += weights.title
    for word in doc.abstract:
        vec[word] += weights.abstract
    return dict(vec)  # convert back to a regular dict

def compute_tfidf(doc, doc_freqs, weights):
    N = max(doc_freqs.values())
    freq = doc_freqs
    tf = compute_tf(doc, doc_freqs, weights)
    
    vec = defaultdict(float)

    # the calculation for IDF(t) was derived from Scikit-Learn which effectively handles edge cases
    for word in doc.author:
        vec[word] += tf[word] * (np.log2((N + 1) / (freq[word] + 1)) + 1) # +1 to prevent divison by zero error
    for word in doc.keyword:
        vec[word] += tf[word] * (np.log2((N + 1)/ (freq[word] + 1)) + 1)
    for word in doc.title:
        vec[word] += tf[word] * (np.log2((N + 1) / (freq[word] + 1)) + 1)
    for word in doc.abstract:
        vec[word] += tf[word] * (np.log2((N + 1) / (freq[word] + 1)) + 1)

    return dict(vec)

def compute_boolean(doc, doc_freqs, weights):
    vec = defaultdict(bool)
    for word in doc.author:
        if doc_freqs[word] > 0:
            vec[word] == 1
        else:
            vec[word] == 0
    for word in doc.keyword:
        if doc_freqs[word] > 0:
            vec[word] == 1
        else:
            vec[word] == 0
    for word in doc.title:
        if doc_freqs[word] > 0:
            vec[word] == 1
        else:
            vec[word] == 0
    for word in doc.abstract:
        if doc_freqs[word] > 0:
            vec[word] == 1
        else:
            vec[word] == 0

    return dict(vec)



### Vector Similarity

def dictdot(x: Dict[str, float], y: Dict[str, float]):
    '''
    Computes the dot product of vectors x and y, represented as sparse dictionaries.
    '''
    keys = list(x.keys()) if len(x) < len(y) else list(y.keys())
    return sum(x.get(key, 0) * y.get(key, 0) for key in keys)

def cosine_sim(x, y):
    '''
    Computes the cosine similarity between two sparse term vectors represented as dictionaries.
    '''
    num = dictdot(x, y)
    if num == 0:
        return 0
    return num / (norm(list(x.values())) * norm(list(y.values())))

    # Suggestion: the computation of cosine similarity can be made more ecient by precomputing and
    # storing the sum of the squares of the term weights for each vector, as these are constants across vector
    # similarity comparisons.

def dice_sim(x, y):
    num = dictdot(x,y)
    if num == 0:
        return 0
    return (2 * num) / (norm(list(x.values())) * norm(list(y.values())))

def jaccard_sim(x, y):
    num = dictdot(x,y)
    if num == 0:
        return 0
    return num / ((norm(list(x.values())) * norm(list(y.values()))) - num)

def overlap_sim(x, y):
    num = dictdot(x,y)
    if num == 0:
        return 0
    return num / min(norm(list(x.values())),  norm(list(y.values())))


### Precision/Recall

def interpolate(x1, y1, x2, y2, x):
    m = (y2 - y1) / (x2 - x1)
    b = y1 - m * x1
    return m * x + b

def get_recalls(results: List[int], relevant: List[int]):
    recalls = list()
    num_relevant = len(relevant)
    for k in range(0, len(relevant) + 1):
        recalls.append(k / num_relevant)
    return recalls

def precision_at(recall: float, results: List[int], relevant: List[int]) -> float:
    '''
    This function should compute the precision at the specified recall level.
    If the recall level is in between two points, you should do a linear interpolation
    between the two closest points. For example, if you have 4 results
    (recall 0.25, 0.5, 0.75, and 1.0), and you need to compute recall @ 0.6, then do something like

    interpolate(0.5, prec @ 0.5, 0.75, prec @ 0.75, 0.6)

    Note that there is implicitly a point (recall=0, precision=1).

    `results` is a sorted list of document ids
    `relevant` is a list of relevant documents

    '''
    if recall == 0: # precision always 0 if recall is
        return 0 

    recalls = get_recalls(results, relevant)

    if recall in recalls:
        num_relevant = len(relevant)
        k = num_relevant * recall # number of correctly retrieved docs
        num_to_retrieve = 0
        counter = 0
        while counter < k:
            if results[num_to_retrieve] in relevant:
                counter += 1
            num_to_retrieve += 1

        B = k

        precision = B / num_to_retrieve
        return precision
    
    else: # interpolate case
        # determine two closest recalls:
        i = 0
        while recalls[i] < recall:
            i += 1
        
        return interpolate(recalls[i - 1], precision_at(recalls[i - 1], results, relevant), 
                           recalls[i], precision_at(recalls[i], results, relevant),
                           recall)

def mean_precision1(results, relevant):
    return (precision_at(0.25, results, relevant) +
        precision_at(0.5, results, relevant) +
        precision_at(0.75, results, relevant)) / 3

def mean_precision2(results, relevant):
    precision = 0
    for i in range(1, 11):
        precision += precision_at(i / 10, results, relevant)
    return precision / 10

def norm_recall(results, relevant):
    N = len(results)
    Rel = len(relevant)

    sum_of_ranks = 0
    for doc in relevant:
        sum_of_ranks += results[doc] + 1 # add 1 since ranks are counted from 1 not 0 and are thus offset by -1 
    sum_i = 0
    for i in range(1, Rel):
        sum_i += i

    return 1 - ((sum_of_ranks - sum_i)/(Rel*(N-Rel)))

def factorial(num):
    if num == 0:
        return 1
    return (num * factorial(num - 1))

def norm_precision(results, relevant):
    N = len(results)
    Rel = len(relevant)

    sum_of_ranks = 0
    sum_i = 0
    for doc in relevant:
        sum_of_ranks += np.log2(results[doc] + 1) # add 1 since ranks are counted from 1 not 0 and are thus offset by -1 
    for i in range(1, Rel):
        sum_i += np.log2(i)

    return 1 - ((sum_of_ranks - sum_i)  / (N * np.log2(N) - (N - Rel) * np.log2(N - Rel) - Rel * np.log2(Rel))) # approximate


### Search
def get_user_settings():
    choice = input('\n Select term weight: (1) tf   (2) tf-idf  (3) boolean')
    while choice != '1' and choice != '2' and choice != '3':
        choice = input('\n Select term weight: (1) tf   (2) tf-idf  (3) boolean')
    if choice == 1:
        term_func = compute_tf
    elif choice == 2:
        term_func = compute_tfidf
    else:
        term_func = compute_boolean

    choice = input('\n Stem tokens? (y/n)')
    while choice != 'y' and choice != 'n':
        choice = input('\n Stem tokens? (y/n)')
    if choice == 'y':
        stem = True
    else:
        stem = False
    
    choice = input('\n Remove stopwords? (y/n)')
    while choice != 'y' and choice != 'n':
        choice = input('\n Remove stopwords? (y/n)')
    if choice == 'y':
        removestop = True
    else:
        removestop = False

    choice = input('\n Select similarity measure: (1) cosine   (2) dice   (3) jaccard   (4) overlap')
    while choice != '1' and choice != '2' and choice != '3' and choice != '4':
        choice = input('\n Select similarity measure: (1) cosine   (2) dice   (3) jaccard   (4) overlap')
    if choice == 1:
        sim = cosine_sim
    elif choice == 2:
        sim = dice_sim
    elif choice == 3:
        sim = jaccard_sim
    elif choice == 4:
        sim = overlap_sim

    author_weight = int(input('\n Enter weight for author: '))
    title_weight = int(input('\n Enter weight for title: '))
    keyword_weight = int(input('\n Enter weight for keyword: '))
    abstract_weight = int(input('\n Enter weight for abstract: '))

    term_weights = TermWeights(author_weight, title_weight, keyword_weight, abstract_weight)
    return term_func, stem, removestop, sim, term_weights

def experiment():
    docs = read_docs('cacm.raw')
    stopwords = read_stopwords('common_words')

    choice = input('\nWould you like to customize the search parameters or use recommended settings? (y/n) ')
    term_func = compute_tfidf
    stem = True
    removestop = True
    sim = cosine_sim
    term_weights = TermWeights(author=1, title=1, keyword=1, abstract=1)
    if choice == 'y':
      term_func, stem, removestop, sim, term_weights = get_user_settings()

    processed_docs = process_docs(docs, stem, removestop, stopwords)
    doc_freqs = compute_doc_freqs(processed_docs)
    doc_vectors = [term_func(doc, doc_freqs, term_weights) for doc in processed_docs]

    author = List[str]
    title = List[str]
    keyword = List[str]
    abstract = List[str]
    query = Document(0, author, title, keyword, abstract)

    print('\nENTER Q AT ANY TIME TO QUIT\n')
    while choice != 'q' and choice != 'Q':
      print('ENTER YOUR QUERIES FOR THE FOLLOWING FIELDS:')

      author_string = input('Author: ')
      choice = author_string
      title_string = input('Title: ')
      choice = title_string
      keyword_string = input('Keyword: ')
      choice = keyword_string
      abstract_string = input('Abstract: ')
      choice = abstract_string

      author = word_tokenize(author_string)
      title = word_tokenize(title_string)
      keyword = word_tokenize(keyword_string)
      abstract = word_tokenize(abstract_string)

      query = Document(0, author, title, keyword, abstract)

      if removestop:
        query = remove_stopwords_doc(query)
      if stem:
        query = stem_doc(query)

      query_vec = term_func(query, doc_freqs, term_weights)
      results = search(doc_vectors, query_vec, sim)

      print('\nHere are the top 10 document ids pertaining to your queries:')
      i = 0
      last_doc = 10
      while i < last_doc:
        print(results[i])
        i += 1
      last_doc += 10

      choice = input('\nWould you like to see the next 10 documents? (y/n) ')
      while (choice == 'y' or choice == 'Y') and i < len(results):
        while i < last_doc:
            print(results[i])
            i += 1
        choice = input('\nWould you like to see the next 10 documents? (y/n) ')
        last_doc += 10
    print('\n')

    return 


def process_docs(docs, stem, removestop, stopwords):
    processed_docs = docs
    if removestop:
        processed_docs = remove_stopwords(processed_docs)
    if stem:
        processed_docs = stem_docs(processed_docs)
    return processed_docs

def search(doc_vectors, query_vec, sim):
    results_with_score = [(doc_id + 1, sim(query_vec, doc_vec))
                    for doc_id, doc_vec in enumerate(doc_vectors)]
    results_with_score = sorted(results_with_score, key=lambda x: -x[1])
    results = [x[0] for x in results_with_score]
    return results


if __name__ == '__main__':
    experiment()