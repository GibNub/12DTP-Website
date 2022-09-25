"""
The Roundtable Hold a forum for Elden Ring players, by an Elden Ring player
A Website for a 12DTP project
"""
# PEP8 --/---------/---------/---------/---------/---------/---------/---------

# std library
import sqlite3
from os import environ
from datetime import datetime
from string import ascii_letters, digits
from dotenv import load_dotenv

# Third party
from flask import Flask, render_template, redirect, url_for, g, session, request, flash, abort
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequestKeyError


# Constant variables
load_dotenv()
SECRET_KEY = environ.get("APP_SECRET_KEY",
                         "4b7603f9b53b1ee7f548c5a4d40b5174249e6ccbfac6914f9c4b7512439bf16c")
USERNAME_WHITELIST = set(ascii_letters + digits + "_")
CATEGORIES = {
    "1": "General",
    "2": "Help",
    "3": "Lore",
    "4": "Humor",
    "5": "News"
}
SORT = {
    "1": "like",
    "2": "dislike"
}
USERNAME_MIN = 3
USERNAME_LIMIT = 20
PASSWORD_MIN = 8
POST_TITLE_LIM = 50



def get_db():
    """Store database connection in a variable"""
    if "db" not in g:
        g.db = sqlite3.connect("forum_database.db")
    return g.db


def today():
    """Easy function to get today's date"""
    # Format is YYYYMMDD with leading zeros for months and days
    # This allows for easy sort by date and string splicing
    post_date = datetime.today().strftime("%Y%m%d")
    return post_date


# Gather the information for forum posts from the database.
# String building may be required in a later date
# All results will be stored as a tuple in a list
# For single item lists, specify with a index of 0
def call_database(query, parameter=None):
    """Simple function to get database"""
    conn = get_db()
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    # Try with parameters
    try:
        cur.execute(query, parameter)
    # Try multiple queries
    except sqlite3.Warning:
        cur.executescript(query)
    # Try without any parameters
    except sqlite3.ProgrammingError:
        cur.execute(query)
    except ValueError:
        cur.execute(query)
    result = cur.fetchall()
    return result


# General query building for home page, posts, comments and replies.
# Take all elements
# Sum the likes and dislikes given from all the users to specified content
# If post, get amount of comments.
# Join user_id for username
# Tells what grade a user has given to a post/reply/comment
# Also apply filters and sorts for posts
# Replies have parent_id so apply if needed.
# Sections of query is ommited if there is no user session
def build_query(content_type,
                user_id,
                condition="",
                order="",
                user_replies=None,
                post_id=None):
    """
    DO NOT USE WITH CUSTOM USER INPUT
    """
    if content_type == "p":
        if user_id:
            query, parameter = f"""SELECT Post.*,
            SUM(CASE WHEN PostGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN PostGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            (SELECT COUNT(Comment.id) FROM Comment
            WHERE Comment.post_id = Post.id)
            AS comment_count,
            UserGrade.grade
            FROM Post
            INNER JOIN User
            ON Post.user_id = User.id
            LEFT JOIN PostGrade
            ON PostGrade.post_id = Post.id
            LEFT JOIN PostGrade AS UserGrade
            ON UserGrade.post_id = Post.id
            AND UserGrade.user_id = ?
            {condition} GROUP BY Post.id {order};""", [user_id]
        else:
            query, parameter = f"""SELECT Post.*,
            SUM(CASE WHEN PostGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN PostGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            (SELECT COUNT(Comment.id) FROM Comment
            WHERE Comment.post_id = Post.id)
            AS comment_count
            FROM Post
            INNER JOIN User
            ON Post.user_id = User.id
            LEFT JOIN PostGrade
            ON PostGrade.post_id = Post.id
            {condition} GROUP BY Post.id {order};""", []
    # Query for comments
    elif content_type == "c":
        if user_replies:
            user_replies = " AND Comment.parent_comment_id IS NOT NULL"
        else:
            user_replies = " AND Comment.parent_comment_id IS NULL"
        if user_id:
            query, parameter = f"""SELECT Comment.*,
            SUM(CASE WHEN CommentGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN CommentGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username,
            UserGrade.grade
            FROM Comment
            INNER JOIN User
            ON Comment.user_id = User.id
            LEFT JOIN CommentGrade
            ON CommentGrade.comment_id = Comment.id
            LEFT JOIN CommentGrade AS UserGrade
            ON UserGrade.comment_id = Comment.id
            AND UserGrade.user_id = ?
            WHERE Comment.post_id = ?
            {user_replies}
            GROUP BY Comment.id;""", [user_id]
        else:
            query, parameter = f"""SELECT Comment.*,
            SUM(CASE WHEN CommentGrade.grade = -1 THEN 1 ELSE 0 END) AS dislike,
            SUM(CASE WHEN CommentGrade.grade = 1 THEN 1 ELSE 0 END) AS like,
            User.username
            FROM Comment
            INNER JOIN User
            ON Comment.user_id = User.id
            LEFT JOIN CommentGrade
            ON CommentGrade.comment_id = Comment.id
            WHERE Comment.post_id = ?
            {user_replies}
            GROUP BY Comment.id;""", []
    else:
        raise Exception(f"type {content_type} is invalid, must be 'c' or 'p'")
    if post_id:
        parameter.append(post_id)
    parameter = tuple(parameter)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, parameter)
    result = cur.fetchall()
    return result


# Delete entry in database
# Used for users, posts, and comments
def delete_entry(delete_type, content_id):
    """
    DO NOT USE FOR USER INPUT
    """
    conn = get_db()
    cur = conn.cursor()
    if delete_type == "p":
        first = "DELETE FROM Post"
    elif delete_type == "c":
        first = "DELETE FROM Comment"
    elif delete_type == "u":
        first = "DELETE FROM User"
    else:
        raise Exception(f"{delete_type} is an invalid type")
    cur.execute(f"{first} WHERE id = ?", (content_id,))
    conn.commit()


# Updates Post table once user submits new post
def update_post(content_type, title, content, date, user_id,):
    """
    Add post to databse
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post
                (type, title, content, user_id, date)
                VALUES (?, ?, ?, ?, ?)""",
                (content_type, title, content, user_id, date))
    conn.commit()


# Updates comments table once user creates a comment or reply
def update_comment(user_id, post_id, content, date, parent_comment_id=None,):
    """
    Add comment to database
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO Comment
                (user_id, post_id, parent_comment_id, content, date)
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, post_id, parent_comment_id, content, date))
    conn.commit()


# Add created user to database
def create_user(username, date, password_hash):
    """
    Add user to database
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO User
                (username, is_admin, join_date, password_hash)
                VALUES (?, False, ?, ?)""",
                (username, date, password_hash))
    conn.commit()


# add / replace given grade to database
def add_grade(user_id, content_type, type_id, user_grade, replace=None):
    """
    Apply user grade to posts/comments
    """
    conn = get_db()
    cur = conn.cursor()
    # Add new grade
    if not replace:
        if content_type == "p":
            query = """INSERT INTO PostGrade (user_id, post_id, grade)
                       VALUES (?, ?, ?);"""
        elif content_type == "c":
            query = """INSERT INTO CommentGrade (user_id, comment_id, grade)
                       VALUES (?, ?, ?);"""
        parameter = (user_id, type_id, user_grade)

    # Replace existing grade
    elif replace:
        if content_type == "p":
            query = """UPDATE PostGrade SET grade = ?
                       WHERE user_id = ? AND post_id = ?;"""
        elif content_type == "c":
            query = """UPDATE CommentGrade SET grade = ?
                       WHERE user_id = ? AND comment_id = ?;"""
        parameter = (user_grade, user_id, type_id)
    cur.execute(query, parameter)
    conn.commit()


# Update user credit when displayed
# Displayed on account page
def user_credit(user_id):
    """
    Calculate user credit then display
    """
    conn = get_db()
    cur = conn.cursor()

    # Calcualte sum of post credits from user
    cur.execute("""SELECT Post.id AS post_id, SUM(PostGrade.grade) FROM Post
                INNER JOIN PostGrade ON PostGrade.post_id = Post.id
                WHERE Post.user_id = ?;""",
                (user_id,))
    post_credit = cur.fetchone()[1]

    # Calcualte sum of comment credits from user
    cur.execute("""SELECT Comment.id AS comment_id, SUM(CommentGrade.grade) FROM Comment
                INNER JOIN CommentGrade ON CommentGrade.comment_id = Comment.id
                WHERE Comment.user_id = ?;""",
                (user_id,))
    comment_credit = cur.fetchone()[1]
    return int(post_credit or 0) + int(comment_credit or 0)


app = Flask(__name__)
app.secret_key = SECRET_KEY

# Homepage has all posts
@app.route("/")
def home():
    """
    Redirect to home page
    """
    # raise Exception("idot") # test 500 error
    user_id = session.get("user_id", None)
    condition = session.get("category", None)
    order_by = session.get("order", None)
    # Check for sorting or filter
    if condition:
        condition_query = f"WHERE Post.type = '{CATEGORIES[condition]}'"
    else:
        condition_query = ""
    if order_by:
        order_by_query = (f"ORDER BY {SORT[order_by]} DESC")
    else:
        order_by_query = "ORDER BY id DESC"
    post = build_query("p", user_id, condition_query, order_by_query)
    return render_template("home.html", post=post, title="Home")


# Creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:content_id>")
def page(content_id):
    """
    Redirect to post page
    """
    user_id = session.get("user_id", None)
    # Check if post is in database
    try:
        post = build_query("p",
                           user_id,
                           condition="WHERE Post.id = ?",
                           post_id=content_id)[0]
    except IndexError:
        abort(404)

    # Get comments and replies of post
    comment = build_query("c", user_id, post_id=content_id)
    user_replies = build_query("c",
                               user_id,
                               post_id=content_id,
                               user_replies=True)

    return render_template("page.html",
                           post=post,
                           comment=comment,
                           user_replies=user_replies,
                           title=post[2])  # Post Title


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    """
    Redirect to reply create page
    """
    # Get comment being replied to
    try:
        reffered_comment = call_database("""SELECT * FROM Comment
                                         WHERE id = ?
                                         AND post_id = ?""",
                                         (comment_id, post_id))[0]
    except IndexError:
        abort(404)
    return render_template("reply.html", comment=reffered_comment, title="Reply To")


# Directs user to the about page
@app.route("/about")
def about():
    """
    Redirect to about page
    """
    return render_template("about.html", title="About")


# Redirect user to either sign in or sign up page.
@app.route("/account/<action>")
def account(action):
    """
    Redirect to log in or sign up
    """
    # Capitalise first letter and remove underscore from url
    try:
        page_title = f"{action[0].upper()}{action[1:4]} {action[5].upper()}{action[6:]}"
    except IndexError:
        abort(404)
    return render_template("sign.html", page=action, title=page_title)


# Goes to account manager
# Calls any relevant database entries
@app.route("/account_management/<int:content_id>")
def dashboard(content_id):
    """
    Redirect to account dashboard
    """
    # Check if user exists
    try:
        user_info = call_database("SELECT * FROM User WHERE id = ?", (content_id,))[0]
    except IndexError:
        abort(404)
    user_id = session.get("user_id", None)
    # Gets user posts
    user_post = call_database("SELECT * FROM Post WHERE user_id = ?", (content_id,))
    # if user is deleted, redirect error
    return render_template("user.html",
                           user_info=user_info,
                           user_post=user_post,
                           content_id=content_id,
                           title=user_info[1],
                           user_id=user_id,
                           user_credit=user_credit(content_id))


# 400 error
@app.errorhandler(CSRFError)
def validation_error(error):
    return render_template("400.html"), 400


# 404 error
@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


# 500 error
@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


# Gets the form values from the home page,
# The variables get updated to the database.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    """
    Add post to database
    """
    if request.method == "POST":
        title = request.form.get("title")
        # Check for title limit
        if len(title) > POST_TITLE_LIM:
            flash("Title length too long", "error")
            return redirect(request.referrer)
        content = request.form.get("content")
        content_type = request.form.get("type")
        if content_type not in [*CATEGORIES.values()]:
            flash("Selected category is not valid", "error")
            return redirect(request.referrer)
        date = today()
        update_post(content_type, title, content, date, session.get("user_id"))
        # Go back to home page so users can easily see their new post
        return redirect(request.referrer)
    return redirect(url_for("home"))


# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    """
    Add comment to database
    """
    if request.method == "POST":
        content = request.form.get("comment_content")
        post_id = request.form.get("post_id")
        date = today()
        update_comment(session.get("user_id"), post_id, content, date)
        return redirect(request.referrer)
    return redirect(url_for("home"))


# Update database with reply
@app.route("/reply", methods=["GET", "POST"])
def reply():
    """
    Add user reply to database
    """
    if request.method == "POST":
        content = request.form.get("content")
        post_id = request.form.get("post_id")
        comment_id = request.form.get("comment_id")
        date = today()
        update_comment(session.get("user_id"), post_id, content, date, comment_id)
        return redirect(url_for("page", content_id=post_id))
    return redirect(url_for("home"))


# Update post or comment with like or dislike.
@app.route("/grade/<int:content_id>/", methods=["GET", "POST"])
def grade(content_id):
    """
    add or replace user grade
    """
    grade_to_int = {
        "Like": 1,
        "Dislike": -1
    }
    if not session.get("user_id", None):
        flash("Create an account to like or dislike", "info")
        return redirect(url_for("account", action="sign_up"))

    if request.method == "POST":
        user_id = session.get("user_id", None)
        table = request.form.get("table")
        user_grade = grade_to_int.get(request.form.get("grade"))
        if user_grade is None:
            return redirect(request.referrer)

        # Find if user already liked or disliked post/comment
        if table == "p":
            query = """SELECT grade FROM PostGrade
                       WHERE user_id = ? AND post_id = ?"""
        elif table == "c":
            query = """SELECT grade FROM CommentGrade
                       WHERE user_id = ? AND comment_id = ?"""
        existing_grade = call_database(query, (user_id, id))

        # Prevent user for giving the same grade to posts/comments.
        # Give grade otherwise
        if not existing_grade:
            add_grade(user_id, table, content_id, user_grade)
        # Change grade if grade already exists
        elif existing_grade[0][0] != user_grade:
            add_grade(user_id, table, content_id, user_grade, True)

        # Build url No section exception
        try:
            section = request.form.get("section")
            url = request.referrer + f"#{str(section)}"
        except BadRequestKeyError:
            url = request.referrer
        return redirect(url)
    return redirect(url_for("home"))


# Creates user account and adds to the database id conditiopns met
# Password is salted and hashed
@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    """
    Create user account then add to db
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        date = today()
        invalid = False
        # Get existing usernames
        # converts result into list without single element tuples
        existing_usernames = [i[0] for i in call_database("SELECT username FROM User")]
        blacklist_characters = [u_letter in USERNAME_WHITELIST for u_letter in username]
        # Check for invalid characters in usernamex
        # Check for invalid lengths in user input
        if not all(blacklist_characters):
            flash("Usernames can only contain A-Z, 0-9, and '_'", "error")
            invalid = True
        elif username in existing_usernames:
            flash("That username already exists", "error")
            invalid = True
        elif len(username) > USERNAME_LIMIT:
            flash("Username must be less than 20 characters", "error")
            invalid = True
        elif len(username) < USERNAME_MIN:
            flash("Usernames must be greater than 3 characters", "error")
            invalid = True
        elif len(password) < PASSWORD_MIN:
            flash("Password must be greater than 8 characters", "error")
            invalid = True
        if invalid:
            return redirect(request.referrer)
        # Create account and add to database
        create_user(username, date,
                    (generate_password_hash(password, salt_length=16)))
        flash("Account created, log in to access your account", "info")
        return redirect(url_for("account", action="sign_in"))
    return redirect(url_for("home"))


# Activates user session if user sucessfuly logs in
@app.route("/sign_in", methods=["GET", "POST"])
def sign_in():
    """
    Create user session when successfuly logged in
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_info = call_database("""SELECT id, username, password_hash, is_admin
                                   FROM User WHERE username = ?""",
                                  (username,))
        # Check for no existing user
        if not user_info:
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        # Check for password
        user_info = user_info[0]
        if not check_password_hash(user_info[2], password):
            flash("Username or password is incorrect", "error")
            return redirect(request.referrer)
        else:
            session["user_id"] = user_info[0]
            session["admin"] = user_info[3]
            flash(f"Logged in successfully as {username}", "info")
            if session.get("admin", None) == 1:
                flash("You account has admin privileges", "info")
    return redirect(url_for("home"))


# Filter posts
@app.route("/sort/<content_type>", methods=["GET", "POST"])
def sort(content_type):
    """
    Apply user defined filters/sort
    """
    if request.method == "POST":
        if content_type == "sort":
            session["category"] = request.form.get("type")
        elif content_type == "order":
            session["order"] = request.form.get("order")
        return redirect(request.referrer)
    return redirect(url_for("home"))


# Log user out
@app.route("/sign_out")
def sign_out():
    """
    Log user and delete user session
    """
    session.pop("user_id", None)
    session.pop("admin", None)
    flash("Successfully logged out", "info")
    return redirect(url_for("home"))


# Delete user, post, or comment
@app.route("/delete", methods=["GET", "POST"])
def delete():
    """
    Delete user content
    """
    if request.method == "POST":
        content_id = request.form.get("id")
        content_type = request.form.get("type")
        if content_type == "u":
            session.pop("user_id", None)
            flash("Account has been deleted successfuly", "info")
        elif content_type == "p":
            flash("Post has been deleted", "info")
        elif content_type == "c":
            flash("Comment has been deleted", "info")
        delete_entry(content_type, content_id)
    return redirect(url_for("home"))


# Close database once app is closed.
@app.teardown_appcontext
def teardown_db(_):
    """
    Teardown db
    """
    get_db().close()


if __name__ == "__main__":
    CSRFProtect().init_app(app)
    app.run(debug=True, host="0.0.0.0", port="8000")
