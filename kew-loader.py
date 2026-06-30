#!/usr/bin/env python3

import argparse
import re
import sqlite3
from graphqlite import Graph
import yt_dlp
import shutil

KEW_MUSIC_DIRECTORY = "~/Music/"
KEW_INSTALL_DIRECTORY = "/tmp/kew-loader/"
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
    nodes = {
            "album": None,
            "songs": [],
            "artist": None,
    }

    print(f"Downloading music from {args.url}")

    ytdl_opts = {
        'extract_flat': True,  # Equivalent to --flat-playlist
        'skip_download': True, # Do not download the media files
        'quiet': True, # No output
    }

    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        info = ytdl.extract_info(args.url, download=False)
        
        if 'entries' in info:
            for entry in info['entries']:
                sources.append(entry)

            nodes["album"] = info["title"]
            nodes["album"] = nodes["album"].replace("Album - ", "")
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
        'outtmpl': f"{KEW_INSTALL_DIRECTORY}%(title)s.%(ext)s",
    }

    graph = Graph(KEW_DB)

    with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
        for i, source in enumerate(sources):
            results = graph.connection.cypher(
                    "MATCH (s:Song {url: $url}) RETURN s LIMIT 1",
                    {"url": source["url"]}
                    )

            if len(results) == 0:
                info = ytdl.extract_info(source['url'], download=False)
                nodes["artist"] = info["artist"] if nodes["artist"] is None else nodes["artist"]
                nodes["songs"].append({
                    "title": info["title"],
                    "url": source["url"],
                    "artists": info["artists"],
                })

    root_is_artist = True if nodes["album"] is None else False

    graph.connection.cypher("""
                         MERGE (a:Artist {name: $name})
                         ON CREATE SET a.name = $name
                         """,
                         {"name": nodes["artist"]})

    if not root_is_artist:
        graph.connection.cypher("""
                             MERGE (a:Artist {name: $name})
                             MERGE (b:Album {title: $title})
                             ON CREATE SET b.title = $title

                             CREATE (a)-[:WROTE]->(b)
                             CREATE (b)-[:WRITTEN_BY]->(a)
                             """,
                             {"name": nodes["artist"], "title": nodes["album"]})

    for song in nodes["songs"]:
        if root_is_artist:
            graph.connection.cypher("""
                                    MERGE (a:Artist {name: $name})
                                    CREATE (s:Song {url: $url})

                                    CREATE (a)-[:WROTE]->(s)
                                    CREATE (s)-[:WRITTEN_BY]->(a)
                                    """,
                                    {"name": nodes["artist"], "url": song["url"]})
        else:
            graph.connection.cypher("""
                                    MERGE (b:Album {title: $title})
                                    CREATE (s:Song {url: $url})

                                    CREATE (b)-[:TRACK]->(s)
                                    CREATE (s)-[:TRACK_OF]->(b)
                                    """,
                                    {"title": nodes["album"], "url": song["url"]})

        for artist in [a for a in song["artists"] if a != nodes["artist"]]:
            graph.connection.cypher("""
                                    MERGE (s:Song {url: $url})
                                    MERGE (a:Artist {name: $name})

                                    CREATE (s)-[:FEATURES]->(a)
                                    CREATE (a)-[:FEATURED]->(s)
                                    """,
                                    {"url": song["url"], "name": artist})


    results = graph.connection.cypher("""
                                      MATCH ()-[r]-()
                                      return r
                                      """)
    for row in results:
        print(f"{row}")
