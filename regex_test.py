import sqlite3
import re

# Connect database and return content of first post
def search_database():
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM Post WHERE id = 1")
    result = cur.fetchall()
    conn.close()
    return result[0]


help = "crucible knight"
found = re.search(r"%s.knig.t" % "crucible", help)

if found:
    print("Found")
else:
    print("Not found")


print(search_database())
search = input("Search for posts\n>>>")