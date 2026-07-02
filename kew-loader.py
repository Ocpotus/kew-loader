#!/usr/bin/env python3

import argparse
from pathlib import Path
import yt_dlp
import sys
from redislite.falkordb_client import FalkorDB

KEW_MUSIC_DIRECTORY = "~/Music"
KEW_DOWNLOAD_DIRECTORY = "/tmp/kew-loader"
KEW_DB = ".kew.db"


if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Download music from Youtube!")
    parser.add_argument(
            "url",
            type=str,
            help="URL to download from"
    )
    args = parser.parse_args()
    sources = []
    nodes = {
            "album": None,
            "songs": [],
            "artist": None,
    }

    print(f"Downloading music from {args.url}")

    ytdl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        info = ytdl.extract_info(args.url, download=False)

        if "entries" in info:
            for entry in info["entries"]:
                sources.append(entry["url"])

            nodes["album"] = info["title"]
            nodes["album"] = nodes["album"].replace("Album - ", "")
        else:
            urls.append(info)

    ytdl_opts = {
        "format": "bestaudio/best",
        "quiet": True, # No output
        "no-warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }
        ],
        "outtmpl": f"{KEW_DOWNLOAD_DIRECTORY}%(title)s.%(ext)s",
    }

    db_client = FalkorDB(str(Path(f"{KEW_MUSIC_DIRECTORY}/{KEW_DB}").expanduser()))
    graph = db_client.select_graph("music")

    # Filter out already added songs
    result = graph.query("""
                         UNWIND $urls as url
                         MATCH (s:Song {url: url})
                         RETURN s
                         """, params={"urls": sources})

    to_add = list(set(sources) - set([r[0].properties["url"] for r in result.result_set]))
    
    if len(to_add) == 0:
        print("All songs are already in Music library...", file=sys.stderr)
        sys.exit()
    
    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        for url in to_add:
                info = ytdl.extract_info(url, download=False)

                if nodes["artist"] is not None:
                    if nodes["artist"] not in info["artist"].split(","):
                        nodes["artist"] = "Various Artists"
                else:
                    nodes["artist"] = info["channel"]

                nodes["songs"].append({
                    "title": info["title"],
                    "url": url,
                    "features": [a for a in info["artists"] if a != nodes["artist"]],
                })
    # Test out
    for song in nodes["songs"]:
        f_path = Path(f"{KEW_DOWNLOAD_DIRECTORY}/{song["title"]}.mp3")
        f_path.touch()

    # Create graph representation
    if nodes["album"] is None:
        result = graph.query("""
                             MERGE (a:Artist {name: $artist})
                             WITH a
                             UNWIND $urls AS url
                             MERGE (s:Song {url: url})
                             MERGE (s)-[:WRITTEN_BY]->(a)
                             MERGE (a)-[:WROTE]->(s)
                             """,
                             params={
                                 "artist": nodes["artist"],
                                 "urls": [i["url"] for i in nodes["songs"]]
                                 }
                             )
    else:
        result = graph.query("""
                             MERGE (a:Artist {name: $artist})
                             MERGE (b:Album {title: $album})
                             MERGE (a)-[:WROTE]->(b)
                             MERGE (b)-[:WRITTEN_BY]->(a)
                             WITH a, b
                             UNWIND $urls AS url
                             MERGE (s:Song {url: url})
                             MERGE (b)-[:TRACK]->(s)
                             MERGE (s)-[:TRACK_OF]->(b)
                             """,
                             params={
                                "artist": nodes["artist"],
                                "album": nodes["album"],
                                "urls": [i["url"] for i in nodes["songs"]]
                                }
                             )

    result = graph.query("""
                         UNWIND $songs AS song
                         MATCH (s:Song {url: song.url})
                         WITH s, song.features AS features 

                         UNWIND features AS feature
                         MERGE (a:Artist {name: feature})

                         MERGE (a)-[:FEATURED]->(s)
                         MERGE (s)-[:FEATURES]->(a)
                         """,
                         params={
                             "songs": nodes["songs"],
                            }
                         )

    db_client.close()

    artist_dir = Path(f"{KEW_MUSIC_DIRECTORY}/{nodes["artist"]}/{nodes["album"]}").expanduser()
    artist_dir.mkdir(parents=True, exist_ok=True)

    for song in nodes["songs"]:
        # Move installed file to proper Artist subdir
        source = Path(f"{KEW_DOWNLOAD_DIRECTORY}/{song["title"]}.mp3").expanduser()
        destination = Path(f"{KEW_MUSIC_DIRECTORY}/{nodes["artist"]}/{nodes["album"]}/{song["title"]}.mp3").expanduser()
        destination.touch()
        source.replace(destination)

        # Create symlink
        for artist in song["features"]:
            dir = Path(f"{KEW_MUSIC_DIRECTORY}/{artist}/").expanduser()
            dir.mkdir(parents=True, exist_ok=True)
            link = Path(f"{KEW_MUSIC_DIRECTORY}/{artist}/{song["title"]}.mp3").expanduser()
            link.symlink_to(destination)
