import hashlib
import json
import os
import re
import bs4
import requests
from bs4 import BeautifulSoup
from collections import Counter
import lxml.html as lh
from string import punctuation
from urllib.parse import urlsplit
from urllib3.exceptions import HTTPError
import dns.resolver
from seoanalyzer.http import http
from seoanalyzer.stemmer import stem
import urllib.robotparser
import advertools as adv
from fake_useragent import UserAgent
from urllib.parse import urlparse

# This list of English stop words is taken from the "Glasgow Information
# Retrieval Group". The original list can be found at
# http://ir.dcs.gla.ac.uk/resources/linguistic_utils/stop_words
ENGLISH_STOP_WORDS = frozenset([
    "a", "about", "above", "across", "after", "afterwards", "again", "against",
    "all", "almost", "alone", "along", "already", "also", "although", "always",
    "am", "among", "amongst", "amoungst", "amount", "an", "and", "another",
    "any", "anyhow", "anyone", "anything", "anyway", "anywhere", "are",
    "around", "as", "at", "back", "be", "became", "because", "become",
    "becomes", "becoming", "been", "before", "beforehand", "behind", "being",
    "below", "beside", "besides", "between", "beyond", "bill", "both",
    "bottom", "but", "by", "call", "can", "cannot", "cant", "co", "con",
    "could", "couldnt", "cry", "de", "describe", "detail", "do", "done",
    "down", "due", "during", "each", "eg", "eight", "either", "eleven", "else",
    "elsewhere", "empty", "enough", "etc", "even", "ever", "every", "everyone",
    "everything", "everywhere", "except", "few", "fifteen", "fify", "fill",
    "find", "fire", "first", "five", "for", "former", "formerly", "forty",
    "found", "four", "from", "front", "full", "further", "get", "give", "go",
    "had", "has", "hasnt", "have", "he", "hence", "her", "here", "hereafter",
    "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his",
    "how", "however", "hundred", "i", "ie", "if", "in", "inc", "indeed",
    "interest", "into", "is", "it", "its", "itself", "keep", "last", "latter",
    "latterly", "least", "less", "ltd", "made", "many", "may", "me",
    "meanwhile", "might", "mill", "mine", "more", "moreover", "most", "mostly",
    "move", "much", "must", "my", "myself", "name", "namely", "neither",
    "never", "nevertheless", "next", "nine", "no", "nobody", "none", "noone",
    "nor", "not", "nothing", "now", "nowhere", "of", "off", "often", "on",
    "once", "one", "only", "onto", "or", "other", "others", "otherwise", "our",
    "ours", "ourselves", "out", "over", "own", "part", "per", "perhaps",
    "please", "put", "rather", "re", "same", "see", "seem", "seemed",
    "seeming", "seems", "serious", "several", "she", "should", "show", "side",
    "since", "sincere", "six", "sixty", "so", "some", "somehow", "someone",
    "something", "sometime", "sometimes", "somewhere", "still", "such",
    "system", "take", "ten", "than", "that", "the", "their", "them",
    "themselves", "then", "thence", "there", "thereafter", "thereby",
    "therefore", "therein", "thereupon", "these", "they",
    "third", "this", "those", "though", "three", "through", "throughout",
    "thru", "thus", "to", "together", "too", "top", "toward", "towards",
    "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us",
    "very", "via", "was", "we", "well", "were", "what", "whatever", "when",
    "whence", "whenever", "where", "whereafter", "whereas", "whereby",
    "wherein", "whereupon", "wherever", "whether", "which", "while", "whither",
    "who", "whoever", "whole", "whom", "whose", "why", "will", "with",
    "within", "without", "would", "yet", "you", "your", "yours", "yourself",
    "yourselves"])

TOKEN_REGEX = re.compile(r'(?u)\b\w\w+\b')

HEADING_TAGS_XPATHS = {
    'h1': '//h1',
    'h2': '//h2',
    'h3': '//h3',
    'h4': '//h4',
    'h5': '//h5',
    'h6': '//h6',
}

ADDITIONAL_TAGS_XPATHS = {
    'title': '//title/text()',
    'meta_desc': '//meta[@name="description"]/@content',
    'viewport': '//meta[@name="viewport"]/@content',
    'charset': '//meta[@charset]/@charset',
    'canonical': '//link[@rel="canonical"]/@href',
    'alt_href': '//link[@rel="alternate"]/@href',
    'alt_hreflang': '//link[@rel="alternate"]/@hreflang',
}

IMAGE_EXTENSIONS = set(['.img', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.avif', ])


class Page():
    """
    Container for each page and the core analyzer.
    """

    def __init__(self, url='', base_domain='', analyze_headings=False, analyze_extra_tags=False):
        """
        Variables go here, *not* outside of __init__
        """

        self.base_domain = urlsplit(base_domain)
        self.parsed_url = urlsplit(url)
        self.url = url
        self.url_length = ''
        self.url_status= ""
        self.url_parameter_status=''
        self.analyze_headings = analyze_headings
        self.analyze_extra_tags = analyze_extra_tags
        self.title = ''
        self.title_status = ''
        self.description = ''
        self.description_status = ''
        self.keywords = {}
        self.content_analysis_status=''
        self.warnings = []
        self.translation = bytes.maketrans(punctuation.encode('utf-8'), str(' ' * len(punctuation)).encode('utf-8'))
        self.links = []
        self.total_word_count = 0
        self.wordcount = Counter()
        self.bigrams = Counter()
        self.trigrams = Counter()
        self.stem_to_word = {}
        self.content_hash = None
        self.image_tag_count = ''
        self.encoding = ''
        self.encoding_status=''
        self.open_graph = {}
        self.og_tags_status = ''
        self.all_link = {}
        self.email_list = []
        self.email_security_status=''
        self.html_type = ''
        self.doctype_status=''
        self.image_miss_tag = []
        self.social_tags = []
        self.meta_keywords = ''
        self.dmarc_status = ''
        self.html_lang = ''
        self.language_status = ''
        self.underscore_count = []
        self.twitter_cards = {}
        self.twitter_cards_status = ''
        self.favicon = ''
        self.favicon_status = ''
        self.custom_error = ''
        self.sitemap_status = {}
        self.overall_score = 0
        self.heading_status = ''
        self.links_overall = {}
        self.schema_type = []
        self.schema_status=''
        self.resolve_url = {}
        self.resolve_url_status = ''
        self.alt_attribute_status = ''
        self.in_page_links_status = ''
        self.xml_sitemaps_status = ''
        self.discovered_pages_status=''
        self.underscores_url_status = ''
        self.canonical_tags=[]
        self.canonical_tags_status = ''

        if analyze_headings:
            self.headings = {}
        if analyze_extra_tags:
            self.additional_info = {}

    def talk(self):
        """
        Returns a dictionary that can be printed
        """

        context = {
            'url': self.url,
            'url_length': self.url_length,
            'url_status':'neutral',
            'url_parameter_status':'neutral',
            'title': self.title,
            'title_status': self.title_status,
            'description': self.description,
            'description_status': self.description_status,
            # 'word_count': self.total_word_count,
            'content_analysis': self.sort_freq_dist(self.keywords, limit=4),
            'content_analysis_status':'neutral',
            # 'bigrams': self.bigrams,
            # 'trigrams': self.trigrams,
            # 'warnings': self.warnings,
            # 'content_hash': self.content_hash,
            'alt_attribute': self.image_miss_tag,
            'image_tag_count': self.image_tag_count,
            'alt_attribute_status': self.alt_attribute_status,
            'encoding': self.encoding,
            'encoding_status':self.encoding_status,
            'schema_org': self.schema_type,
            'schema_org_status':self.schema_status,
            'open_graph_item': self.open_graph,
            'og_tags_status': self.og_tags_status,
            'twitter_item': self.twitter_cards,
            'twitter_card_status': self.twitter_cards_status,
            'all_link': self.all_link,
            'over_all': self.links_overall,
            'in_page_links_status': self.in_page_links_status,
            'email_list': self.email_list,
            'email_security_status':'neutral',
            'doctype': self.html_type,
            'doctype_status':'neutral',
            'declared_language': self.html_lang,
            'language_status': self.language_status,
            'social_tags': self.social_tags,
            'meta_keywords': self.meta_keywords,
            'dmarc_status': self.dmarc_status,
            'underscores_url': self.underscore_count,
            'underscores_url_status': self.underscores_url_status,
            'favicon': self.favicon,
            'favicon_status': self.favicon_status,
            'custom_404_status': self.custom_error,
            'xml_sitemaps': self.sitemap_status,
            'xml_sitemaps_status': self.xml_sitemaps_status,
            'discovered_pages_status':'neutral',
            'resolveurlarray': self.resolve_url,
            'resolve_url_status': self.resolve_url_status,
            'overall_score': self.overall_score,
            'headings_status': self.heading_status,
            'canonical_tags':self.canonical_tags,
            'canonical_tags_status': self.canonical_tags_status
        }

        if self.analyze_headings:
            context['headings'] = self.headings
        if self.analyze_extra_tags:
            context['additional_info'] = self.additional_info

        return context

    def populate(self, bs):

        """
        Populates the instance variables from BeautifulSoup
        """

        # feeds = bs.findAll(type='application/rss+xml') + bs.findAll(type='application/atom+xml')
        # for feed in feeds:
        #     href=feed.get('href')
        #     print(feed)
        self.url_length = len(self.url)
        url_error = f'{self.url}/nonexistent_path'
        error_res = requests.get(url_error)
        if error_res.status_code == 404:
            self.custom_error = 'good'
        else:
            self.custom_error = "bad"
        parsed_url = urllib.parse.urlparse(self.url)
        parsed_url = parsed_url.netloc
        try:
            favicon_bs = bs.find('link', attrs={'rel': re.compile("^(shortcut icon|icon)$", re.I)})
            self.favicon = favicon_bs['href']
            if 'www' or 'http' or 'https' not in self.favicon:
                self.favicon = f'{parsed_url}/{self.favicon}'
            else:
               pass

        except:
            favicon_url = f'{self.url}/favicon.ico'
            b = requests.get(favicon_url)
            if b.status_code == 200:
                self.favicon = favicon_url
            else:
                self.favicon = None
        if self.favicon != None:
            self.overall_score = self.overall_score + 2
            self.favicon_status = 'good'
        else:
            self.favicon_status = 'bad'

        try:
            self.html_lang = bs.html['lang']
        except:
            self.html_lang = ''
        if self.html_lang != '':
            self.overall_score = self.overall_score + 2
            self.language_status = 'good'
        else:
            self.language_status = 'bad'
        temp_domain = self.base_domain.netloc
        analyse_domain = temp_domain.replace('www.', '')
        try:
            test_dmarc = dns.resolver.resolve('_dmarc.' + analyse_domain, 'TXT')
            for dns_data in test_dmarc:
                if 'DMARC1' in str(dns_data):
                    self.dmarc_status = 'good'
        except:
            self.dmarc_status = 'bad'
        try:
            self.title = bs.title.text
        except AttributeError:
            pass
        if len(self.title) >= 40 and len(self.title) <= 40:
            self.overall_score = self.overall_score + 6
            self.title_status = 'good'
        elif len(self.title) <= 40:
            self.overall_score = self.overall_score + 4
            self.title_status = 'improve'
        elif len(self.title) >= 60:
            self.title_status = 'bad'
        try:
            items = [item for item in bs.contents if isinstance(item, bs4.Doctype)]
            self.html_type = items[0]
        except:
            self.html_type = 'default html'


        descr = bs.findAll('meta', attrs={'name': 'description'})

        if len(descr) > 0:
            self.description = descr[0].get('content')
        try:
            if len(self.description) >= 140 and len(self.description) <= 156:
                self.overall_score = self.overall_score + 6
                self.description_status = 'good'
            elif len(self.description) >= 50 and len(self.description) <= 140:
                self.overall_score = self.overall_score + 4
                self.description_status = 'Improve'
            elif len(self.description) >= 156 or len(self.description) <= 50:
                self.description_status = 'bad'
        except:
            pass

        keywords = bs.find('meta', attrs={'name': 'keywords'})
        try:
            self.meta_keywords = (keywords.get('content'))
        except:
            self.meta_keywords = None
        if keywords == None:
            pass

    def analyze_heading_tags(self, bs):
        """
        Analyze the heading tags and populate the headings
        """
        json_schema = bs.find('script', attrs={'type': 'application/ld+json'})
        if json_schema != None:
            json_dat = json.loads(json_schema.contents[0])

            try:
                sch_type = json_dat['@type']
                self.schema_type.append(sch_type)
            except:
                sch_type = (json_dat['@graph'][0]['@type'])
                self.schema_type.extend(sch_type)
        else:
            pass
        if self.schema_type != []:
            self.overall_score = self.overall_score + 4
            self.schema_status = 'good'
        else:
            self.schema_status = 'bad'
        try:
            site = bs.find('meta', attrs={'name': re.compile(r'^twitter:site')})
            self.twitter_cards['site'] = site.get('content')
        except:
            self.twitter_cards['site'] = None
        try:
            title = bs.find('meta', attrs={'name': re.compile(r'^twitter:title')})
            self.twitter_cards['title'] = title.get('content')
        except:
            self.twitter_cards['title'] = None
        try:
            description = bs.find('meta', attrs={'name': re.compile(r'^twitter:description')})
            self.twitter_cards['description'] = description.get('content')
        except:
            self.twitter_cards['description'] = None
        try:
            image = bs.find('meta', attrs={'name': re.compile(r'^twitter:image')})
            self.twitter_cards['image'] = image.get('content')
        except:
            self.twitter_cards['image'] = None
        if self.twitter_cards['site'] and self.twitter_cards['title'] and self.twitter_cards['description'] != None:
            self.overall_score = self.overall_score + 2
            self.twitter_cards_status = 'good'
        else:
            self.twitter_cards_status = 'bad'
        try:
            dom = lh.fromstring(str(bs))
        except ValueError as _:
            dom = lh.fromstring(bs.encode('utf-8'))
        for tag, xpath in HEADING_TAGS_XPATHS.items():
            value = [heading.text_content() for heading in dom.xpath(xpath)]
            if value:
                self.headings.update({tag: value})

    def analyze_additional_tags(self, bs):
        """
        Analyze additional tags and populate the additional info
        """
        robots_url = f'{self.url}robots.txt'
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        sitemap_var = rp.site_maps()
        if sitemap_var == None:
            sitemap_checker = ['wp-sitemap.xml', 'sitemap_index.xml', 'sitemap.xml']
            sitemap_true = []
            for i in sitemap_checker:
                sitemap1 = f'{self.url}/{i}'
                user_agent = UserAgent()
                user_agent = user_agent.random
                user_agent = {"User-Agent": user_agent}
                a = requests.get(sitemap1, headers=user_agent)
                if a.status_code == 200:
                    sitemap_true.append(sitemap1)
                    break
                else:
                    pass
            if [] != sitemap_true:
                url_list1 = adv.sitemap_to_df(sitemap_true[0])
                try:
                    url_sitemap1 = len(url_list1['loc'].tolist())
                except:
                    url_sitemap1 = 0
                self.sitemap_status['sitemap'] = sitemap_true[0]
                self.sitemap_status['url_found'] = url_sitemap1
                self.sitemap_status['present_in_robots'] = False
            else:
                self.sitemap_status['sitemap'] = None
                self.sitemap_status['url_found'] = 0
                self.sitemap_status['present_in_robots'] = False
        else:
            url_list = adv.sitemap_to_df(sitemap_var[0])
            try:
                url_sitemap = len(url_list['loc'].tolist())
            except:
                url_sitemap = 0
            self.sitemap_status['sitemap'] = sitemap_var[0]
            self.sitemap_status['url_found'] = url_sitemap
            self.sitemap_status['present_in_robots'] = True
        if self.sitemap_status['sitemap'] != None:
            self.overall_score = self.overall_score + 6
            self.xml_sitemaps_status = 'good'
        else:
            self.xml_sitemaps_status = 'bad'
        try:
            dom = lh.fromstring(str(bs))
        except ValueError as _:
            dom = lh.fromstring(bs.encode('utf-8'))
        for tag, xpath in ADDITIONAL_TAGS_XPATHS.items():
            value = dom.xpath(xpath)
            self.additional_info.update({tag: value})
        if self.additional_info['canonical'] !=[]:
            self.overall_score = self.overall_score + 6
            self.canonical_tags_status = 'good'
            self.canonical_tags=self.additional_info['canonical']
        else:
            self.canonical_tags_status = 'bad'


    def analyze(self, raw_html=None):
        """
        Analyze the page and populate the warnings list
        """

        if not raw_html:
            valid_prefixes = []

            # only allow http:// https:// and //
            for s in ['http://', 'https://', '//', ]:
                valid_prefixes.append(self.url.startswith(s))

            if True not in valid_prefixes:
                self.warn(f'{self.url} does not appear to have a valid protocol.')
                return

            if self.url.startswith('//'):
                self.url = f'{self.base_domain.scheme}:{self.url}'

            if self.parsed_url.netloc != self.base_domain.netloc:
                self.warn(f'{self.url} is not part of {self.base_domain.netloc}.')
                return

            try:
                page = http.get(self.url)
            except HTTPError as e:
                self.warn(f'Returned {e}')
                return

            encoding = 'ascii'

            if 'content-type' in page.headers:
                encoding = page.headers['content-type'].split('charset=')[-1]
                self.encoding = True

            if encoding.lower() not in ('text/html', 'text/plain', 'utf-8'):
                # there is no unicode function in Python3
                # try:
                #     raw_html = unicode(page.read(), encoding)
                # except:
                self.encoding = False
                return
            else:
                raw_html = page.data.decode('utf-8')
            if self.encoding == True:
                self.encoding_status = 'good'
            else:
                self.encoding_status = 'bad'
        self.content_hash = hashlib.sha1(raw_html.encode('utf-8')).hexdigest()

        # remove comments, they screw with BeautifulSoup
        clean_html = re.sub(r'<!--.*?-->', r'', raw_html, flags=re.DOTALL)

        soup_lower = BeautifulSoup(clean_html.lower(), 'html.parser')  # .encode('utf-8')
        soup_unmodified = BeautifulSoup(clean_html, 'html.parser')  # .encode('utf-8')

        texts = soup_lower.findAll(text=True)
        visible_text = [w for w in filter(self.visible_tags, texts)]

        self.process_text(visible_text)

        self.populate(soup_lower)

        self.analyze_title()
        self.analyze_description()
        self.analyze_og(soup_lower)
        self.analyze_a_tags(soup_unmodified)
        self.analyze_img_tags(soup_lower)
        self.analyze_h1_tags(soup_lower)

        if self.analyze_headings:
            self.analyze_heading_tags(soup_unmodified)
        if self.analyze_extra_tags:
            self.analyze_additional_tags(soup_unmodified)

        return True

    def word_list_freq_dist(self, wordlist):
        freq = [wordlist.count(w) for w in wordlist]
        return dict(zip(wordlist, freq))

    def sort_freq_dist(self, freqdist, limit=1):
        aux = [(freqdist[key], self.stem_to_word[key]) for key in freqdist if freqdist[key] >= limit]
        aux.sort()
        aux.reverse()
        return aux

    def raw_tokenize(self, rawtext):
        return TOKEN_REGEX.findall(rawtext.lower())

    def tokenize(self, rawtext):
        return [word for word in TOKEN_REGEX.findall(rawtext.lower()) if word not in ENGLISH_STOP_WORDS]

    def getngrams(self, D, n=2):
        return zip(*[D[i:] for i in range(n)])

    def process_text(self, vt):
        page_text = ''

        for element in vt:
            if element.strip():
                page_text += element.strip().lower() + u' '

        tokens = self.tokenize(page_text)
        raw_tokens = self.raw_tokenize(page_text)
        self.total_word_count = len(raw_tokens)

        bigrams = self.getngrams(raw_tokens, 2)

        for ng in bigrams:
            vt = ' '.join(ng)
            self.bigrams[vt] += 1

        trigrams = self.getngrams(raw_tokens, 3)

        for ng in trigrams:
            vt = ' '.join(ng)
            self.trigrams[vt] += 1

        freq_dist = self.word_list_freq_dist(tokens)

        for word in freq_dist:
            root = stem(word)
            cnt = freq_dist[word]

            if root not in self.stem_to_word:
                self.stem_to_word[root] = word

            if root in self.wordcount:
                self.wordcount[root] += cnt
            else:
                self.wordcount[root] = cnt

            if root in self.keywords:
                self.keywords[root] += cnt
            else:
                self.keywords[root] = cnt

    def analyze_og(self, bs):
        """
        Validate open graph tags
        """

        parsed_url = urllib.parse.urlparse(self.url)
        parsed_url = parsed_url.netloc

        internal_links = []
        for a in bs.find_all('a', href=True):
            if len(a['href'].strip()) > 1 and a['href'][0] != '#' and 'javascript:' \
                    not in a['href'].strip() and 'mailto:' not in a['href'].strip() and 'tel:' not in a['href'].strip():
                if parsed_url in a["href"] or a["href"].startswith("/") or a['href'].endswith('.html'):
                    if urlparse(self.url).netloc.lower() not in a['href']:
                        a["href"] = f'{urlparse(self.url).netloc.lower()}/{a["href"]}'


                        internal_links.append(
                            [a.get_text(), a["href"].replace('//','/'), "nofollow"] if "nofollow" in str(a) else [a.get_text(), a["href"],
                                                                                               "follow"])
                    else:
                        internal_links.append(
                            [a.get_text(), a["href"], "nofollow"] if "nofollow" in str(a) else [a.get_text(), a["href"],
                                                                                                "follow"])
        #
        if len(internal_links) <= 200:
            self.overall_score = self.overall_score + 4
            self.in_page_links_status = 'good'
        else:
            self.in_page_links_status = 'bad'

        external_links = []
        for a in bs.find_all('a', href=True):
            if parsed_url not in a["href"] and not a["href"].startswith("/") and not a["href"].startswith("./") and not \
            a["href"].startswith("#") and not a['href'].endswith('.html'):
                if 'http' in a['href'].strip() or 'https' in a['href'].strip():
                    external_links.append(
                        [a.get_text(), a["href"], "nofollow"] if "nofollow" in str(a) else [a.get_text(), a["href"],
                                                                                            "follow"])
        self.links_overall['Internal_link'] = internal_links
        self.links_overall['External_link'] = external_links
        og_title = bs.find('meta', attrs={'property': 'og:title'})
        og_description = bs.find('meta', attrs={'property': 'og:description'})
        og_image = bs.find('meta', attrs={'property': 'og:image'})
        og_site_name = bs.find('meta', attrs={'property': 'og:site_name'})
        og_url = bs.find('meta', attrs={'property': 'og:url'})
        og_type = bs.find('meta', attrs={'property': 'og:type'})
        if (og_title) == None:
            self.open_graph['og_title'] = None
        else:
            self.open_graph['og_title'] = (og_title.get('content'))
        if (og_description) == None:
            self.open_graph['og_description'] = None
        else:
            self.open_graph['og_description'] = og_description.get('content')
        if (og_image) == None:
            self.open_graph['og_image'] = None
        else:
            self.open_graph['og_image'] = og_image.get('content')
        if (og_site_name) == None:
            self.open_graph['og_site_name'] = None
        else:
            self.open_graph['og_site_name'] = og_site_name.get('content')
        if (og_url) == None:
            self.open_graph['og_url'] = None
        else:
            self.open_graph['og_url'] = og_url.get('content')
        if (og_type) == None:
            self.open_graph['og_type'] = None
        else:
            self.open_graph['og_type'] = og_type.get('content')
        if self.open_graph['og_site_name'] and self.open_graph['og_title'] and self.open_graph[
            'og_description'] != None:
            self.overall_score = self.overall_score + 2
            self.og_tags_status = 'good'
        else:
            self.og_tags_status = 'bad'

    def analyze_title(self):
        """
        Validate the title
        """

        # getting lazy, create a local variable so save having to
        # type self.x a billion times
        t = self.title

        # calculate the length of the title once
        length = len(t)

        domain = urlparse(self.url).netloc
        try:
            domain_parsed = domain.replace('www.', '')
        except:
            domain_parsed = domain
        url1 = f"https://www.{domain_parsed}"
        url2 = f'http://www.{domain_parsed}'
        url3 = f'https://{domain_parsed}'
        url4 = f'http://{domain_parsed}'
        list_url = [url1, url2, url3, url4]
        urls_list = []
        status_code_list = []
        not_reslved = []
        for i in list_url:
            req = requests.get(i)
            not_reslved.append(i)
            status_code_list.append(req.status_code)
            urls_list.append(req.url)
        self.resolve_url['url'] = not_reslved
        self.resolve_url['status_code'] = status_code_list
        self.resolve_url['redirected_url'] = urls_list
        if 403 not in status_code_list:
            self.overall_score = self.overall_score + 6
            self.resolve_url_status = 'good'
        else:
            self.resolve_url_status = 'bad'

        if length == 0:
            self.warn(u'Missing title tag')
            return
        elif length < 10:
            self.warn(u'Title tag is too short (less than 10 characters): {0}'.format(t))
        elif length > 70:
            self.warn(u'Title tag is too long (more than 70 characters): {0}'.format(t))

    def analyze_description(self):
        """
        Validate the description
        """

        # getting lazy, create a local variable so save having to
        # type self.x a billion times
        d = self.description

        # calculate the length of the description once
        length = len(d)

        if length == 0:
            self.description = 'Missing description'
            return
        elif length < 140:
            self.warn(u'Description is too short (less than 140 characters): {0}'.format(d))
        elif length > 255:
            self.warn(u'Description is too long (more than 255 characters): {0}'.format(d))

    def visible_tags(self, element):
        if element.parent.name in ['style', 'script', '[document]']:
            return False

        return True

    def analyze_img_tags(self, bs):
        """
        Verifies that each img has an alt and title
        """

        images = bs.find_all('img')
        try:
            images_len = len(images)
            self.image_tag_count = images_len
        except:
            self.image_tag_count = 0
        for image in images:
            src = ''
            if 'src' in image:
                src = image['src']
            elif 'data-src' in image:
                src = image['data-src']
            else:
                src = image

            if len(image.get('alt', '')) == 0:
                try:
                    self.image_miss_tag.append(src.get('src'))
                except:
                    self.image_miss_tag.append(src.get('data-src'))
        if self.image_miss_tag == []:
            self.overall_score = self.overall_score + 4
            self.alt_attribute_status = 'good'
        else:
            self.alt_attribute_status = 'bad'

    def analyze_h1_tags(self, bs):
        """
        Make sure each page has at least one H1 tag
        """
        try:
            email_tags = re.compile(r'([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+){0,}')
            self.email_list.extend(set([x for x in bs.strings if email_tags.search(x).group()]))
        except:
          pass
        htags = bs.find_all('h1')

        if len(htags) == 0:
            self.warn('Each page should have at least one h1 tag')
        h1_tag_val = []
        for i in htags:
            h1_tag_val.append(i.text)
        if len(htags) != 0 and len(h1_tag_val) == 1:
            self.overall_score = self.overall_score + 4
            self.heading_status = 'good'
        else:
            self.heading_status = 'bad'

    def analyze_a_tags(self, bs):
        """
        Add any new links (that we didn't find in the sitemap)
        """
        anchors = bs.find_all('a', href=True)
        url_list = []
        url_title = []
        for tag in anchors:
            tag_href = tag['href']
            tag_text = tag.text.lower().strip()
            url_title.append(tag_text)
            url_list.append(tag_href)

            if len(tag.get('title', '')) == 0:
                continue

            if tag_text in ['click here', 'page', 'article']:
                continue

            if self.base_domain.netloc not in tag_href and ':' in tag_href:
                continue

            modified_url = self.rel_to_abs_url(tag_href)

            url_filename, url_file_extension = os.path.splitext(modified_url)

            # ignore links to images
            if url_file_extension in IMAGE_EXTENSIONS:
                continue

            # remove hash links to all urls
            if '#' in modified_url:
                modified_url = modified_url[:modified_url.rindex('#')]

            self.links.append(modified_url)
        for i in url_list:
            if "_" in i:
                self.underscore_count.append(i)
            else:
                pass
        if self.underscore_count == []:
            self.overall_score = self.overall_score + 2
            self.underscores_url_status = 'good'
        else:
            self.underscores_url_status = 'bad'
        self.all_link = len(url_list)

        subs = ['facebook', 'instagram', 'twitter', 'linkedin']
        social_tag = [s for s in url_list if any(i in s for i in subs)]
        self.social_tags.extend(social_tag)

    def rel_to_abs_url(self, link):
        if ':' in link:
            return link

        relative_path = link
        domain = self.base_domain.netloc

        if domain[-1] == '/':
            domain = domain[:-1]

        if len(relative_path) > 0 and relative_path[0] == '?':
            if '?' in self.url:
                return f'{self.url[:self.url.index("?")]}{relative_path}'

            return f'{self.url}{relative_path}'

        if len(relative_path) > 0 and relative_path[0] != '/':
            relative_path = f'/{relative_path}'

        return f'{self.base_domain.scheme}://{domain}{relative_path}'

    def warn(self, warning):
        self.warnings.append(warning)
