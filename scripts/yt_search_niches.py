#!/usr/bin/env python3
"""Search YouTube for business niche videos and save results."""
import subprocess, json, sys, os, time

NICHES = {
    # Wave 1
    "PHARMACY":    ["аптека бизнес как открыть", "аптечный бизнес ошибки с нуля"],
    "DENTAL":      ["стоматология бизнес как открыть", "стоматологический кабинет бизнес ошибки"],
    "MANICURE":    ["маникюрный салон бизнес как открыть", "ногтевой сервис бизнес ошибки"],
    "BAKERY":      ["пекарня бизнес как открыть", "пекарня с нуля ошибки опыт"],
    "FITNESS":     ["фитнес клуб бизнес как открыть", "тренажерный зал бизнес ошибки"],
    "COMPCLUB":    ["компьютерный клуб бизнес как открыть", "кибер клуб бизнес ошибки"],
    "PIZZA":       ["пиццерия бизнес как открыть", "пиццерия с нуля ошибки опыт"],
    "SUSHI":       ["суши бар бизнес как открыть", "суши доставка бизнес ошибки"],
    "FURNITURE":   ["мебельный цех бизнес как открыть", "производство мебели бизнес ошибки"],
    "TIRESERVICE": ["шиномонтаж бизнес как открыть", "шиномонтаж с нуля ошибки опыт"],
    "FLOWERS":     ["цветочный магазин бизнес как открыть", "цветочный бизнес ошибки"],
    "PETSHOP":     ["зоомагазин бизнес как открыть", "зоомагазин с нуля ошибки опыт"],
    "KIDSCENTER":  ["детский центр бизнес как открыть", "детский развивающий центр ошибки"],
    "LAUNDRY":     ["прачечная бизнес как открыть", "химчистка бизнес ошибки"],
    # Wave 2
    "AUTOSERVICE": ["автосервис бизнес как открыть", "СТО бизнес ошибки с нуля"],
    "BEAUTY":      ["салон красоты бизнес как открыть", "салон красоты ошибки с нуля"],
    "PHOTO":       ["фотостудия бизнес как открыть", "фотостудия бизнес ошибки"],
    "PRINTING":    ["типография бизнес как открыть", "полиграфия бизнес ошибки"],
    "HOTEL":       ["мини отель бизнес как открыть", "хостел бизнес ошибки"],
    "CATERING":    ["кейтеринг бизнес как открыть", "кейтеринг бизнес ошибки"],
}

def yt_search(query, n=10):
    try:
        r = subprocess.run(
            [sys.executable, '-m', 'yt_dlp',
             f'ytsearch{n}:{query}',
             '--flat-playlist', '--no-warnings', '-j'],
            capture_output=True, timeout=45)
        vids = []
        for line in r.stdout.decode('utf-8', 'replace').strip().split('\n'):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                vids.append({
                    'id': d.get('id', ''),
                    'title': d.get('title', ''),
                    'channel': d.get('channel', ''),
                    'views': d.get('view_count', 0) or 0,
                    'duration': d.get('duration_string', ''),
                })
            except:
                pass
        return vids
    except Exception as e:
        print(f"  error: {e}", file=sys.stderr)
        return []

def main():
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge', 'niches')
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, '_yt_videos.json')

    all_results = {}
    total = len(NICHES)

    for i, (niche_id, queries) in enumerate(NICHES.items(), 1):
        print(f"[{i}/{total}] {niche_id}...")
        seen_ids = set()
        videos = []
        for q in queries:
            results = yt_search(q)
            for v in results:
                if v['id'] not in seen_ids:
                    seen_ids.add(v['id'])
                    videos.append(v)
            time.sleep(1)  # be polite

        # Sort by views descending, keep top 15
        videos.sort(key=lambda x: x['views'], reverse=True)
        videos = videos[:15]
        all_results[niche_id] = videos
        print(f"  found {len(videos)} unique videos (top: {videos[0]['views']:,} views)" if videos else "  no videos found")

    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_file}")
    print(f"Total: {sum(len(v) for v in all_results.values())} videos across {len(all_results)} niches")

if __name__ == '__main__':
    main()
