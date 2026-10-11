from rcf import analyze_file
from rcf.baseline import keyword_rank
from rcf.kb import load_cards


def test_every_card_has_all_sections():
    cards = load_cards()
    assert len(cards) >= 8
    for c in cards:
        assert c.id and c.title and c.symptoms and c.cause and c.fix


def test_keyword_baseline_ranks_disk_full_first(data_path):
    ranked = keyword_rank(analyze_file(data_path("disk_full_40.log")).records)
    assert ranked[0]["category"] == "disk_full"
    assert ranked[0]["lines"][0] == 27


def test_keyword_baseline_ssh(data_path):
    ranked = keyword_rank(analyze_file(data_path("ssh_bruteforce_30.log")).records)
    assert ranked[0]["category"] == "ssh_bruteforce"


def test_chroma_search_finds_the_right_card():
    from rcf.kb import KnowledgeBase

    kb = KnowledgeBase(chroma_dir=None)  # in-memory Chroma
    assert kb.search("nginx: bind() to 0.0.0.0:80 failed (98: Address already in use)")[0][0].id == "port_in_use"
    assert kb.search("Could not resolve host: example.com")[0][0].id == "dns_failure"
    assert len(kb.search("anything", k=3)) == 3
