#!/usr/bin/env python3

import argparse
import re
import sqlite3
from graphqlite import Graph
import yt_dlp


KEW_DB = "kew-db.db"

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

    print(f"Downloading music from {args.url}")

    ytdl_opts = {
        'extract_flat': True,  # Equivalent to --flat-playlist
        'skip_download': True, # Do not download the media files
        'quiet': True, # No output
    }

    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        info = ytdl.extract_info(args.url, download=False)
        
        # Iterate through individual entries in the playlist
        if 'entries' in info:
            for entry in info['entries']:
                sources.append(entry)
        else:
            urls.append(info)

    ytdl_opts = {
        # Extract the best quality audio
        'format': 'bestaudio/best',
        'quiet': True, # No output
        'no-warnings': True,
        
        # Convert to mp3 or m4a using FFmpeg
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            # This postprocessor writes metadata tags (Artist, Album, etc.) directly into the file
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }
        ],
        # Name the file nicely based on track/title
        'outtmpl': '%(title)s.%(ext)s',
    }

    graph = Graph(KEW_DB)

    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        for i, source in enumerate(sources):
            results = graph.connection.cypher(
                    "MATCH (s:Song {url: $url}) RETURN s LIMIT 1",
                    {"url": source["url"]}
                    )

            if len(results) == 0:
                print(source)
                pass
                """
                print(f"Downloading {source['title']}")
                info = ytdl.extract_info(args.url, download=False)
                safe = ytdl.sanitize_info(info)
                nodes = {
                        "album": safe["album"],
                        "artists": safe["artists"],
                        "duration": safe["duration_string"],
                        }
                """
