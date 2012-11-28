import uuid
from flask import Flask, request, jsonify, json
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import desc
import time

__author__ = 'nubela'
SQL_URI = 'postgresql://nubela@localhost/coderage'
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQL_URI
db = SQLAlchemy(app)

#--- db schema ---

class CRUser(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    username = db.Column(db.Unicode(255))
    solved_puzzles_count = db.Column(db.Integer)


class Puzzle(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    user_id = db.Column(db.Unicode(255), db.ForeignKey('cr_user.id'))
    incomplete_puzzle = db.Column(db.Unicode(255))
    complete_puzzle = db.Column(db.Unicode(255))
    timestamp = db.Column(db.Float)

    @property
    def serialize(self):
        return {
            "puzzle": json.unloads(self.incomplete_puzzle),
            "id": self.id
        }


class SolvedPuzzle(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    created_user_id = db.Column(db.Unicode(255), db.ForeignKey('cr_user.id'))
    puzzle_id = db.Column(db.Unicode(255), db.ForeignKey('puzzle.id'))
    timestamp = db.Column(db.Float)

#--- api endpoints ---

@app.route('/user', methods=['PUT'])
def put_user():
    username = request.args.get("username", None)

    #check error
    if get_user_username(username) is not None:
        return jsonify({
            "status": "error",
            "error": "user alr exists"
        })

    if username is None:
        return jsonify({
            "status": "error",
            "error": "no username provided"
        })

    #create the user
    user = CRUser()
    user.id = generate_uuid()
    user.username = username
    user.solved_puzzles_count = 0
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "status": "ok",
        "user_id": user.id,
    })


@app.route('/user/ranks', methods=['get'])
def get_user_ranks():
    users = (db.session.query(CRUser).
             order_by(desc(CRUser.solved_puzzles_count))
        )
    all_users = users.all()
    serialized_users = []
    for rank, u in enumerate(all_users):
        serialized_users += {
            "rank": rank,
            "username": u.username,
        }

    return jsonify({
        "status": "ok",
        "puzzle_rankings": serialized_users
    })


@app.route('/sudoku/puzzle', methods=['PUT'])
def put_sudoku_puzzle():
    user_id = request.args.get("user_id", None)
    incomplete_puzzle_json = request.args.get("incomplete_puzzle", None)
    complete_puzzle_json = request.args.get("complete_puzzle", None)
    complete_puzzle = json.loads(complete_puzzle_json) if complete_puzzle_json is not None else None
    user = get_user_userid(user_id)

    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})

    if incomplete_puzzle_json is None or complete_puzzle_json is None:
        return jsonify({"status": "error", "error": "missing puzzles"})

    if not proper_puzzle(complete_puzzle):
        return jsonify({"status": "error", "error": "invalid puzzle"})

    puzzle = Puzzle()
    puzzle.id = generate_uuid()
    puzzle.complete_puzzle = complete_puzzle_json
    puzzle.incomplete_puzzle = incomplete_puzzle_json
    puzzle.user_id = user_id
    puzzle.timestamp = time.time()
    db.session.add(puzzle)
    db.session.commit()
    return ({
                "status": "ok"
            })


@app.route('/sudoku/puzzles', methods=['GET'])
def get_sudoku_puzzle():
    user_id = request.args.get("user_id", None)
    user = get_user_userid(user_id)

    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})

    total_puzzles_uploaded = db.session.query(Puzzle).filter(Puzzle.user_id == user_id).count()
    puzzles = db.session.query(Puzzle).filter(Puzzle.user_id != user_id).order_by(Puzzle.timestamp).limit(
        total_puzzles_uploaded)

    return jsonify({"status": "ok",
                    "puzzles": [p.serialize for p in puzzles]})


@app.route('/sudoku/puzzle', methods=['POST'])
def post_sudoku_puzzle():
    user_id = request.args.get("user_id", None)
    puzzle_id = request.args.get("puzzle_id", None)
    completed_puzzle_json = request.args.get("complete_puzzle", None)

    user = get_user_userid(user_id)

    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})

    puzzle = get_puzzle(puzzle_id)
    incomplete_puzzle = json.loads(puzzle.incomplete_puzzle)
    completed_puzzle = json.loads(completed_puzzle_json)
    if matches_puzzle(incomplete_puzzle, completed_puzzle):
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": "bad puzzle solution"})

#--- util methods ---

def generate_uuid():
    return str(uuid.uuid1())


def get_user_username(username):
    return db.session.query(CRUser).filter(CRUser.username == username).first()


def get_user_userid(user_id):
    return db.session.query(CRUser).filter(CRUser.id == user_id).first()


def get_puzzle(puzzle_id):
    return db.session.query(Puzzle).filter(Puzzle.id == puzzle_id).first()


def proper_puzzle(puzzle_dic):
    """
    Checks that this sudoku puzzle fulfills the puzzle constraints and hence is a valid puzzle
    """
    #rows
    rows = [set(puzzle_dic[x:9]) for x in range(9)]
    cols = [set(puzzle_dic[x::9]) for x in range(9)]
    subsquares = []
    for i in range(9):
        general_row = i / 3
        general_col = (i % 3) * 3
        s = set()
        rows = [rows[j] for j in range(general_row, general_row+3)]
        for r in rows:
            for k in range(general_col, general_col+3):
                s.add(r[k])
        subsquares += [s]
    for r in rows:
        if len(r) < 9: return False
    for c in cols:
        if len(c) < 9: return False
    for s in subsquares:
        if len(s) < 9: return False
    return True

def matches_puzzle(incomplete_puzzle, completed_puzzle):
    """
    Checks that the incomplete puzzle is a subset of the completed puzzle
    """
    for idx, val in incomplete_puzzle:
        if val == 0: continue
        if completed_puzzle[idx] != val: return False
    return True

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)