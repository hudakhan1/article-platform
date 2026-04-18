import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from flask import Flask,request,flash,redirect,url_for,render_template,session
import random, yagmail

import re
from flask import jsonify
import os
from werkzeug.utils import secure_filename

from collections import Counter
import datetime
datetime.datetime.now()

cre=credentials.Certificate(r"C:\Users\kasha\Desktop\article platform\article-platform-c2895-firebase-adminsdk-fbsvc-f5352268b4.json")

firebase_admin.initialize_app(cre,{
    'databaseURL':'https://article-platform-c2895-default-rtdb.firebaseio.com/'
})


app=Flask(__name__)
app.secret_key = "456"



@app.route("/")
def home():
    return render_template("article.html")

@app.route('/article')
def article():
    return render_template('article.html')


# Folder for uploads
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','jfif'}


# USER SIGNUP
@app.route('/user_signup', methods=['POST', 'GET'])
def user_signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        profile_pic = request.files.get('profile_pic')

        if not name or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for('user_signup'))

        # Save profile picture if uploaded
        profile_pic_path = None
        if profile_pic and profile_pic.filename != "":
            filename = secure_filename(profile_pic.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            profile_pic.save(filepath)
            profile_pic_path = filepath  # yeh db mai save hoga

        # Save to Firebase
        users_ref = db.reference('users')
        new_user_ref = users_ref.push({
            'name': name,
            'email': email,
            'password': password,
            'profile_pic': profile_pic_path if profile_pic_path else ""
        })

        # Save uid in session
        session['uid'] = new_user_ref.key

        flash("Signup successful! Please login.", "success")
        return redirect(url_for('user_login'))

    return render_template('login_signup.html')


# USER LOGIN
@app.route('/user_login', methods=['POST', 'GET'])
def user_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role')

        if not email or not password or not role:
            flash("All fields are required", "error")
            return redirect(url_for('user_login'))

        if role == "user":
            users_ref = db.reference('users').get()
            if users_ref:
                for uid, user_data in users_ref.items():
                    if user_data.get('email') == email and user_data.get('password') == password:
                        # ✅ Session set
                        session['uid'] = uid
                        session['email'] = email

                        # ✅ User ko online mark karo
                        db.reference(f'users/{uid}').update({
                            "status": "online",
                            "last_seen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })

                        flash("Login successful!", "success")
                        return redirect(url_for('user_dashboard'))
            flash("Invalid user credentials", "error")
            return redirect(url_for('user_login'))

        elif role == "admin":
            admin_data = db.reference('admin').get()
            if admin_data:
                db_email = str(admin_data.get('email', '')).strip()
                db_password = str(admin_data.get('password', '')).strip()
                if db_email == email and db_password == password:
                    session['role'] = 'admin'
                    session['uid'] = 'admin'

                    flash("Admin login successful!", "success")
                    return redirect(url_for('admin_dashboard'))

            flash("Invalid admin credentials", "error")
            return redirect(url_for('user_login'))

    return render_template('login_signup.html')

#forget_Pass
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
        # Get current step from URL or default to email
        step = request.args.get('step', 'email')

        # ----------------
        # STEP 1: Email + Role
        # ----------------
        if step == 'email':
            if request.method == 'POST':
                role = request.form.get('role', '').strip().lower()
                email = request.form.get('email', '').strip().lower()

                if not role or not email:
                    flash("Please select role and enter email", "error")
                    return redirect(url_for('forgot_password', step='email'))

                ref = db.reference('admins') if role == 'admin' else db.reference('users')
                data = ref.get()

                if not data:
                    flash("No account found", "error")
                    return redirect(url_for('forgot_password', step='email'))

                # Find UID by email
                uid = None
                for k, v in data.items():
                    if v.get('email', '').lower() == email:
                        uid = k
                        break

                if not uid:
                    flash("Email not found", "error")
                    return redirect(url_for('forgot_password', step='email'))

                # Save in session
                session['reset_uid'] = uid
                session['reset_role'] = role

                # Generate & save verification code
                code = str(random.randint(100000, 999999))
                session['reset_code'] = code

                try:
                    yag = yagmail.SMTP('saharax191@gmail.com', 'ctravpkafztcmjiu')
                    yag.send(to=email, subject="Password Reset Code", contents=f"Your verification code is: {code}")
                except Exception as e:
                    flash("Failed to send email. Try again.", "error")
                    return redirect(url_for('forgot_password', step='email'))

                flash("Verification code sent", "info")
                return redirect(url_for('forgot_password', step='verify'))

            return render_template('forgot_password.html')

        # ----------------
        # STEP 2: Verify Code
        # ----------------
        elif step == 'verify':
            # If no session data, force back to email step
            if 'reset_code' not in session:
                flash("Session expired. Please try again.", "error")
                return redirect(url_for('forgot_password', step='email'))

            if request.method == 'POST':
                entered_code = request.form.get('code', '').strip()

                if entered_code == session.get('reset_code'):
                    return redirect(url_for('forgot_password', step='confirm'))
                else:
                    flash("Invalid verification code", "error")
                    return redirect(url_for('forgot_password', step='verify'))

            return render_template('verification.html')

        # ----------------
        # STEP 3: Confirm Password
        # ----------------
        elif step == 'confirm':
            # If no session UID/role, send back
            if 'reset_uid' not in session or 'reset_role' not in session:
                flash("Session expired. Please try again.", "error")
                return redirect(url_for('forgot_password', step='email'))

            if request.method == 'POST':
                new_password = request.form.get('password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()

                if not new_password or not confirm_password:
                    flash("Please fill both password fields", "error")
                    return redirect(url_for('forgot_password', step='confirm'))

                if new_password != confirm_password:
                    flash("Passwords do not match", "error")
                    return redirect(url_for('forgot_password', step='confirm'))

                uid = session['reset_uid']
                role = session['reset_role']

                ref = db.reference(f'admins/{uid}') if role == 'admin' else db.reference(f'users/{uid}')
                ref.update({'password': new_password})

                # Clear session
                session.clear()

                flash("Password updated successfully,Please log in with your new password.", "success")
                return redirect(url_for('user_login'))

            return render_template('confirm_password.html')

        else:
            return redirect(url_for('forgot_password', step='email'))












@app.route('/user_dashboard')
def user_dashboard():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']

    # Current user data
    current_user = db.reference(f'users/{uid}').get()

    # All users
    users_ref = db.reference("users").get() or {}

    # All posts
    all_posts = db.reference("posts").get() or {}

    posts_list = []
    for owner_uid, owner_posts in all_posts.items():
        if not owner_posts:
            continue
        for post_id, post_val in owner_posts.items():
            if not isinstance(post_val, dict):
                continue
            post = dict(post_val)
            post['id'] = post_id
            post['owner'] = owner_uid

            # Likes
            likes = post.get("likes") or {}
            post['likes'] = likes if isinstance(likes, dict) else {}
            post['is_liked'] = uid in post['likes']

            # Comments
            post['comments'] = post.get('comments') or {}

            posts_list.append(post)

    # Randomize posts like Facebook
    import random
    random.shuffle(posts_list)

    return render_template('user_dashboard.html', user=current_user, posts=posts_list, users=users_ref)


@app.route("/admin_dashboard")
def admin_dashboard():
    return "Welcome Admin"



#edit user
#edit user
@app.route('/edit_user', methods=['GET', 'POST'])
def edit_user():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']
    user_ref = db.reference(f'users/{uid}')
    user_data = user_ref.get()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()   # <-- Name field add
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        profile_pic = request.files.get('profile_pic')

        updates = {}

        if name:
            updates['name'] = name   # <-- Update user name
        if email:
            updates['email'] = email
        if password:
            updates['password'] = password
        if profile_pic and profile_pic.filename != "":
            filename = secure_filename(profile_pic.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            profile_pic.save(filepath)
            updates['profile_pic'] = filepath

        if updates:
            user_ref.update(updates)
            flash("Profile updated successfully!", "success")
        else:
            flash("No changes made", "info")

        return redirect(url_for('edit_user'))

    # Pass user data to template
    return render_template("edit_user.html", user=user_data)





#posts
@app.route('/post', methods=['GET', 'POST'])
def create_post():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        image = request.files.get('image')
        video = request.files.get('video')  # ✅ video bhi nikal liya

        if not content and (not image or image.filename == "") and (not video or video.filename == ""):
            flash("Write something or upload an image/video", "error")
            return redirect(url_for('create_post'))

        image_path, video_path = None, None

        # ✅ Save image agar di gayi hai
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            image.save(filepath)
            image_path = filepath

        # ✅ Save video agar diya gaya hai
        if video and video.filename != "":
            video_filename = secure_filename(video.filename)
            video_filepath = os.path.join(UPLOAD_FOLDER, video_filename)
            video.save(video_filepath)
            video_path = video_filepath

        # ✅ Post data
        post_data = {
            "content": content,
            "image": image_path if image_path else "",
            "video": video_path if video_path else "",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # ✅ Save to Firebase under user's UID
        posts_ref = db.reference(f'posts/{uid}')
        posts_ref.push(post_data)

        flash("Post created successfully!", "success")
        return redirect(url_for('create_post'))

    return render_template('post.html')

#edit post


UPLOAD_FOLDER = "static/uploads"


@app.route('/edit_post/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']
    post_ref = db.reference(f'posts/{uid}/{post_id}')
    post_data = post_ref.get()

    if not post_data:
        flash("Post not found", "error")
        return redirect(url_for('create_post'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        image = request.files.get('image')
        video = request.files.get('video')

        updates = {}

        if content:
            updates['content'] = content

        # Handle new image
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            image.save(filepath)
            updates['image'] = filepath

        # Handle new video
        if video and video.filename != "":
            filename = secure_filename(video.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            video.save(filepath)
            updates['video'] = filepath

        if updates:
            post_ref.update(updates)
            flash("Post updated successfully!", "success")
        else:
            flash("No changes made", "info")

        return redirect(url_for('edit_post', post_id=post_id))

    return render_template('edit_post.html', post=post_data, post_id=post_id)


#delete post
# Delete Post
@app.route('/delete_post/<post_id>', methods=['GET', 'POST'])
def delete_post(post_id):
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']

    # Post ka reference
    post_ref = db.reference(f'posts/{uid}/{post_id}')
    post_data = post_ref.get()

    if not post_data:
        flash("Post not found or you don’t have permission.", "error")
        return redirect(url_for('my_profile'))

    if request.method == 'POST':
        # Agar user confirm kare to delete kar do
        post_ref.delete()
        flash("Post deleted successfully!", "success")
        return redirect(url_for('my_profile'))

    # Agar GET request hai to confirmation page dikhana hai
    return render_template('delete_post.html', post=post_data, post_id=post_id)




# My Profile

@app.route('/my_profile')
def my_profile():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']

    # Get current user
    user_ref = db.reference(f'users/{uid}')
    user_data = user_ref.get()
    if not user_data:
        flash("User not found", "error")
        return redirect(url_for('user_login'))

    # Get all users (for commenter names/profile pics)
    users_ref = db.reference('users').get() or {}

    # Get only current user's posts
    user_posts = db.reference(f'posts/{uid}').get() or {}

    posts_list = []
    for post_id, post_val in (user_posts.items() if isinstance(user_posts, dict) else []):
        if not isinstance(post_val, dict):
            continue
        post = dict(post_val)
        post['id'] = post_id
        post['owner'] = uid
        post['content'] = post.get('content', "")
        post['image'] = post.get('image', "")
        post['video'] = post.get('video', "")

        likes = post.get('likes') or {}
        post['likes'] = likes
        post['is_liked'] = uid in likes

        post['comments'] = post.get('comments') or {}

        posts_list.append(post)

    # Sort by date descending
    posts_list = sorted(posts_list, key=lambda x: x.get('date', ''), reverse=True)

    return render_template('my_profile.html', user=user_data, posts=posts_list, users=users_ref)

#likes
@app.route('/like_post/<owner_uid>/<post_id>', methods=['POST'])
def like_post(owner_uid, post_id):
    if 'uid' not in session:
        return {"error": "Login required"}, 401

    user_uid = session['uid']

    # ✅ Nested path: posts/{owner_uid}/{postId}
    post_ref = db.reference(f'posts/{owner_uid}/{post_id}')
    post_data = post_ref.get()
    if not post_data:
        return {"error": "Post not found"}, 404

    likes_ref = post_ref.child("likes")
    likes = likes_ref.get() or {}

    if user_uid in likes:
        # already liked -> unlike
        likes_ref.child(user_uid).delete()
    else:
        # like
        likes_ref.update({user_uid: True})

    updated_likes = likes_ref.get() or {}
    return {"count": len(updated_likes), "liked": user_uid in updated_likes}

#comments


import uuid

@app.route('/add_comment/<owner_uid>/<post_id>', methods=['POST'])
def add_comment(owner_uid, post_id):
    if 'uid' not in session:
        return {"error": "Login required"}, 401

    user_uid = session['uid']
    data = request.get_json()
    comment_text = data.get("comment", "").strip()

    if not comment_text:
        return {"error": "Empty comment"}, 400

    # Generate unique comment id
    comment_id = str(uuid.uuid4())

    # Current time
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save in DB
    comment_ref = db.reference(f'posts/{owner_uid}/{post_id}/comments/{comment_id}')
    comment_ref.set({
        "uid": user_uid,
        "comment": comment_text,
        "date": now
    })

    # Get user info for display
    user_data = db.reference(f'users/{user_uid}').get()

    return {
        "uid": user_uid,
        "name": user_data.get("name"),
        "profile_pic": user_data.get("profile_pic"),
        "comment": comment_text,
        "date": now,
        "comment_id": comment_id  # yeh zaroori hai
    }

@app.route('/add_reply/<owner_uid>/<post_id>/<comment_id>', methods=['POST'])
def add_reply(owner_uid, post_id, comment_id):
    if 'uid' not in session:
        return jsonify({"error": "Not logged in"}), 403

    uid = session['uid']
    data = request.get_json()
    text = data.get("reply", "").strip()

    if not text:
        return jsonify({"error": "Empty reply"}), 400

    reply_id = str(uuid.uuid4())
    reply_data = {
        "uid": uid,
        "reply": text,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    }

    ref = db.reference(f"posts/{owner_uid}/{post_id}/comments/{comment_id}/replies/{reply_id}")
    ref.set(reply_data)

    # --- increment comment count (include replies) ---
    post_ref = db.reference(f"posts/{owner_uid}/{post_id}")
    post = post_ref.get()
    current_count = post.get("comment_count", 0)
    post_ref.update({"comment_count": current_count + 1})

    # get user info
    user = db.reference(f'users/{uid}').get()

    return jsonify({
        "reply_id": reply_id,
        "uid": uid,
        "name": user.get("name", "Unknown"),
        "profile_pic": user.get("profile_pic", "uploads/default.png"),
        "reply": text,
        "date": reply_data["date"]
    })


@app.route('/edit_comment/<owner_uid>/<post_id>/<comment_id>', methods=['POST'])
def edit_comment(owner_uid, post_id, comment_id):
    if 'uid' not in session:
        return jsonify({"error": "Login required"}), 403

    uid = session['uid']
    data = request.get_json()
    new_text = data.get("comment", "").strip()

    if not new_text:
        return jsonify({"error": "Empty comment"}), 400

    ref = db.reference(f'posts/{owner_uid}/{post_id}/comments/{comment_id}')
    comment_data = ref.get()

    if not comment_data:
        return jsonify({"error": "Comment not found"}), 404

    # Sirf creator ya post owner edit kar sakta hai
    post_ref = db.reference(f'posts/{owner_uid}/{post_id}')
    post_data = post_ref.get()

    if comment_data["uid"] != uid and owner_uid != uid:
        return jsonify({"error": "Not allowed"}), 403

    ref.update({"comment": new_text})
    return jsonify({"success": True, "comment": new_text})




@app.route('/edit_reply/<owner_uid>/<post_id>/<comment_id>/<reply_id>', methods=['POST'])
def edit_reply(owner_uid, post_id, comment_id, reply_id):
    if 'uid' not in session:
        return jsonify({"error": "Login required"}), 403

    uid = session['uid']
    data = request.get_json()
    new_text = data.get("reply", "").strip()

    if not new_text:
        return jsonify({"error": "Empty reply"}), 400

    ref = db.reference(f'posts/{owner_uid}/{post_id}/comments/{comment_id}/replies/{reply_id}')
    reply_data = ref.get()

    if not reply_data:
        return jsonify({"error": "Reply not found"}), 404

    # Sirf creator ya post owner edit kar sakta hai
    post_ref = db.reference(f'posts/{owner_uid}/{post_id}')
    post_data = post_ref.get()

    if reply_data["uid"] != uid and owner_uid != uid:
        return jsonify({"error": "Not allowed"}), 403

    ref.update({"reply": new_text})
    return jsonify({"success": True, "reply": new_text})


# Delete Comment
@app.route("/delete_comment/<owner_uid>/<post_id>/<comment_id>", methods=["DELETE"])
def delete_comment(owner_uid, post_id, comment_id):
    if "uid" not in session:
        return jsonify({"error": "Login required"}), 401

    current_uid = session["uid"]
    comment_ref = db.reference(f"posts/{owner_uid}/{post_id}/comments/{comment_id}")
    comment_data = comment_ref.get()

    if not comment_data:
        return jsonify({"error": "Comment not found"}), 404

    # Only comment owner OR post owner can delete
    if comment_data.get("uid") != current_uid and owner_uid != current_uid:
        return jsonify({"error": "Not allowed"}), 403

    # Count replies to adjust counter
    replies = comment_data.get("replies", {})
    removed_count = 1 + len(replies)

    comment_ref.delete()

    return jsonify({"success": True, "removed_count": removed_count})


@app.route("/delete_reply/<owner_uid>/<post_id>/<comment_id>/<reply_id>", methods=["DELETE"])
def delete_reply(owner_uid, post_id, comment_id, reply_id):
    if "uid" not in session:
        return jsonify({"error": "Login required"}), 401

    current_uid = session["uid"]
    reply_ref = db.reference(f"posts/{owner_uid}/{post_id}/comments/{comment_id}/replies/{reply_id}")
    reply_data = reply_ref.get()

    if not reply_data:
        return jsonify({"error": "Reply not found"}), 404

    # Only reply owner OR post owner can delete
    if reply_data.get("uid") != current_uid and owner_uid != current_uid:
        return jsonify({"error": "Not allowed"}), 403

    reply_ref.delete()

    return jsonify({"success": True, "removed_count": 1})

@app.route('/all_users')
def all_users():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    # Get all users from Firebase
    users_ref = db.reference('users').get() or {}

    # Convert to list for easy loop in HTML
    users_list = []
    for uid, user_data in users_ref.items():
        if isinstance(user_data, dict):
            users_list.append({
                "uid": uid,
                "name": user_data.get("name"),
                "profile_pic": user_data.get("profile_pic", "static/default.png")
            })

    return render_template('all_users.html', users=users_list)


@app.route('/send_chat_request/<receiver_uid>', methods=['POST'])
def send_chat_request(receiver_uid):
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    sender_uid = session['uid']
    sender_data = db.reference(f'users/{sender_uid}').get()

    if not sender_data:
        flash("Sender data not found", "error")
        return redirect(url_for('all_users'))

    # Save request under receiver
    request_ref = db.reference(f'chat_requests/{receiver_uid}/{sender_uid}')
    existing_request = request_ref.get()

    if existing_request:
        flash("You already sent a request to this user.", "info")
    else:
        request_ref.set({
            "status": "pending",
            "name": sender_data.get("name"),
            "profile_pic": sender_data.get("profile_pic", "static/default.png")
        })
        flash("Chat request sent!", "success")

    return redirect(url_for('all_users'))


@app.route('/message_requests')
def message_requests():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    current_uid = session['uid']
    requests_ref = db.reference(f'chat_requests/{current_uid}').get() or {}

    requests_list = []
    for sender_uid, data in requests_ref.items():
        if isinstance(data, dict) and data.get("status") == "pending":
            requests_list.append({
                "sender_uid": sender_uid,
                "name": data.get("name"),
                "profile_pic": data.get("profile_pic", "static/default.png"),
            })

    return render_template("message_requests.html", requests=requests_list)


@app.route('/handle_request/<sender_uid>/<action>', methods=['POST'])
def handle_request(sender_uid, action):
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    current_uid = session['uid']
    request_ref = db.reference(f'chat_requests/{current_uid}/{sender_uid}')

    if action == "accept":
        request_ref.update({"status": "accepted"})
        flash("Request accepted! You can now chat.", "success")
    elif action == "reject":
        request_ref.update({"status": "rejected"})
        flash("Request rejected.", "info")

    return redirect(url_for("message_requests"))



@app.route('/messenger')
def messenger():
    if 'uid' not in session:
        flash("Please login first", "error")
        return redirect(url_for('user_login'))

    uid = session['uid']

    # Get all chat requests where status = accepted
    requests_ref = db.reference('chat_requests').get() or {}

    accepted_users = []
    for receiver_uid, senders in requests_ref.items():
        for sender_uid, req in (senders or {}).items():
            if req.get("status") == "accepted":
                # If I am sender or receiver
                if uid in [receiver_uid, sender_uid]:
                    # Get the "other" person
                    other_uid = receiver_uid if uid == sender_uid else sender_uid

                    # Get user profile
                    user_data = db.reference(f'users/{other_uid}').get()
                    if user_data:
                        accepted_users.append({
                            "uid": other_uid,
                            "name": user_data.get("name"),
                            "profile_pic": user_data.get("profile_pic", "static/default.png")
                        })

    return render_template("messenger.html", users=accepted_users)





@app.route('/chat/<other_uid>')
def chat_room(other_uid):
    if 'uid' not in session:
        return redirect(url_for('user_login'))

    uid = session['uid']
    room_id = "_".join(sorted([uid, other_uid]))

    other_user = db.reference(f'users/{other_uid}').get() or {}

    return render_template("chat_room.html", other_user=other_user, room_id=room_id, uid=uid)


@app.route('/get_messages/<room_id>')
def get_messages(room_id):
    messages_ref = db.reference(f'chats/{room_id}/messages').get() or {}
    messages = []
    keys = []
    if messages_ref:
        for key, msg in messages_ref.items():
            keys.append(key)
            messages.append(msg)
    return jsonify({"messages": messages, "keys": keys})


@app.route('/send_message/<room_id>', methods=['POST'])
def send_message(room_id):
    if 'uid' not in session:
        return jsonify({"status": "error", "msg": "Not logged in"})

    uid = session['uid']
    data = request.get_json(force=True)
    text = data.get("message", "").strip()
    if not text:
        return jsonify({"status": "error", "msg": "Empty message"})

    msg_ref = db.reference(f'chats/{room_id}/messages').push()
    msg_ref.set({
        "sender": uid,
        "text": text,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "seen": False
    })

    return jsonify({"status": "success"})


@app.route('/mark_seen/<room_id>/<msg_id>', methods=['POST'])
def mark_seen(room_id, msg_id):
    db.reference(f'chats/{room_id}/messages/{msg_id}').update({"seen": True})
    return jsonify({"status": "success"})



# Logout
@app.route('/logout')
def logout():
    if 'uid' in session and session['uid'] != 'admin':
        uid = session['uid']
        user_ref = db.reference(f'users/{uid}')
        user_ref.update({
            "status": "offline",
            "last_seen": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('user_login'))



@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    if 'uid' not in session:
        return {"error": "Not logged in"}, 403

    uid = session['uid']
    data = request.get_json()
    show_status = data.get("show_status", True)

    user_ref = db.reference(f'users/{uid}')
    user_ref.update({"show_status": show_status})

    return {"success": True, "show_status": show_status}

@app.context_processor
def inject_user():
    uid = session.get('uid')
    if uid and uid != 'admin':
        user = db.reference(f'users/{uid}').get()
        if user:
            user['uid'] = uid
            return dict(user=user)
    return dict(user=None)





if __name__=='__main__':
    app.run(debug=True)