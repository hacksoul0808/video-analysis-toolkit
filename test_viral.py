import sys
sys.path.insert(0, r'g:\video-analysis-toolkit')
from server.services.ranking_service import _fetch_douyin_viral
r = _fetch_douyin_viral()
print('Videos:', len(r['videos']))
print('Error:', r.get('error'))
for v in r['videos'][:10]:
    print(f"  #{v['rank']} {v['title'][:40]:40s} | 赞:{v['digg_count']:>8} 转:{v['share_count']:>6} 评:{v['comment_count']:>5} | {v['author']}")
