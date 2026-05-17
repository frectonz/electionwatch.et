from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from yt_dlp import YoutubeDL

fana_medrek = [
    "https://www.youtube.com/watch?v=Isdiet0C9FA",
    "https://www.youtube.com/watch?v=4byg_qME7DQ",
    "https://www.youtube.com/watch?v=RNSXsJhPT7k",
    "https://www.youtube.com/watch?v=IJSgkVaFq6U",
    "https://www.youtube.com/watch?v=ihYTmV3w38o",
    "https://www.youtube.com/watch?v=j9HL-v6Akjs",
    "https://www.youtube.com/watch?v=l7XtNS_znDc",
    "https://www.youtube.com/watch?v=3zRbfhtT4IQ",
    "https://www.youtube.com/watch?v=qzkCHpL1DJw",
]

etv_nebe = [
    "https://www.youtube.com/watch?v=BPDQbsjWZ94",
    "https://www.youtube.com/watch?v=3r4-I5zVvqg",
    "https://www.youtube.com/watch?v=Gulr8Kw8-cQ",
    "https://www.youtube.com/watch?v=aNQccF3jTT4",
    "https://www.youtube.com/watch?v=9JcOOksO7Ok",
    "https://www.youtube.com/watch?v=sKmJysWP-Kw",
    "https://www.youtube.com/watch?v=ABmWjAn_Cyk",
    "https://www.youtube.com/watch?v=UNvv-R93bok",
    "https://www.youtube.com/watch?v=uXeJS1Tory0",
    "https://www.youtube.com/watch?v=-lZqsvPkYLY",
]

api = YouTubeTranscriptApi()
formatter = JSONFormatter()

ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
}
ydl = YoutubeDL(ydl_opts)


def get_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return query["v"][0]


def load_transcript(video_id: str, path: Path):
    print(f"Loading transcript for {video_id}...")
    transcript = api.fetch(video_id, languages=["am"])
    formatted = formatter.format_transcript(transcript, ensure_ascii=False, indent=2)
    path.write_text(formatted, encoding="utf-8")
    print(f"Wrote transcript to {path}.")


def get_upload_date(video_url: str) -> str | None:
    info = ydl.extract_info(video_url, download=False)
    return info["upload_date"]


def load_transcripts(prefix: str, links: list[str]):
    for link in links:
        video_id = get_video_id(link)
        if not video_id:
            print(f"Failed to extract video ID from '{link}'")
            continue

        upload_date = get_upload_date(link)
        if not upload_date:
            print(f"Failed to get upload date for '{video_id}'")
            continue

        path = Path(f"data/{prefix}/{upload_date}-{video_id}.json")

        load_transcript(video_id, path)


def main():
    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/fana_medrek").mkdir(parents=True, exist_ok=True)
    Path("data/etv_nebe").mkdir(parents=True, exist_ok=True)

    load_transcripts("fana_medrek", fana_medrek)
    load_transcripts("etv_nebe", etv_nebe)


if __name__ == "__main__":
    main()
    ydl.close()
