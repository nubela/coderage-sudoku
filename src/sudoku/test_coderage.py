"""
Unit tests for CodeRage API Platform
"""
import unittest
import urllib
from flask import json
from sudoku.coderage import new_user, random_string, new_puzzle, new_solution_record, db, app


__author__ = 'nubela'


class CodeRageTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client(db)
        self.sample_puzzle = [
            0, 0, 0, 2, 6, 0, 7, 0, 1,
            6, 8, 0, 0, 7, 0, 0, 9, 0,
            1, 9, 0, 0, 0, 4, 5, 0, 0,
            8, 2, 0, 1, 0, 0, 0, 4, 0,
            0, 0, 4, 6, 0, 2, 9, 0, 0,
            0, 5, 0, 0, 0, 3, 0, 2, 8,
            0, 0, 9, 3, 0, 0, 0, 7, 4,
            0, 4, 0, 0, 5, 0, 0, 3, 6,
            7, 0, 3, 0, 1, 8, 0, 0, 0
        ]
        self.sample_puzzle_solution = [
            4, 3, 5, 2, 6, 9, 7, 8, 1,
            6, 8, 2, 5, 7, 1, 4, 9, 3,
            1, 9, 7, 8, 3, 4, 5, 6, 2,
            8, 2, 6, 1, 9, 5, 3, 4, 7,
            3, 7, 4, 6, 8, 2, 9, 1, 5,
            9, 5, 1, 7, 4, 3, 6, 2, 8,
            5, 1, 9, 3, 2, 6, 8, 7, 4,
            2, 4, 8, 9, 5, 7, 1, 3, 6,
            7, 6, 3, 4, 1, 8, 2, 5, 9
        ]
        self.sample_fail_puzzle_1 = range(80)
        self.sample_fail_puzzle_2 = range(82)
        self.sample_fail_puzzle_3 = [0] + [10 for i in range(80)]
        self.sample_fail_puzzle_3 = [0, 1, 1] + [10 for i in range(78)]

    def _test_register_user(self):
        """
        Tests the API endpoint POST:/user/ for a user self-registering
        """
        #post data
        data = {"username": "nubela"}
        resp = self.client.put("/user/", data=data)
        resp_dict = json.loads(resp.data)
        assert resp_dict["status"] == "ok"

    def _test_upload_puzzle(self):
        """
        Tests that a proper puzzle with its corresponding solution can be properly uploaded
        """
        user_obj = new_user(random_string())
        data = {"user_id": user_obj.id,
                "incomplete_puzzle": json.dumps(self.sample_puzzle),
                "complete_puzzle": json.dumps(self.sample_puzzle_solution)}
        resp = self.client.put("/sudoku/puzzle/", data=data)
        resp_dict = json.loads(resp.data)
        assert resp_dict["status"] == "ok"


    def _test_get_puzzles(self):
        """
        Tests that fetch puzzles work, and that they dont belong to us.
        and that if we fetched 2, they should return 2
        """
        a_user_obj = new_user("a")
        b_user_obj = new_user("b")
        p1 = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), a_user_obj.id)
        p2 = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), a_user_obj.id)
        p3 = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), b_user_obj.id)
        p4 = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), b_user_obj.id)
        p5 = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), b_user_obj.id)
        data = {"user_id": a_user_obj.id}
        resp = self.client.get("/sudoku/puzzle/?" + urllib.urlencode(data))
        resp_dict = json.loads(resp.data)
        puzzle_ids = [p['id'] for p in resp_dict['puzzles']]
        assert resp_dict["status"] == "ok"
        assert len(resp_dict["puzzles"]) == 2
        db.session.add(p3)
        db.session.add(p4)
        db.session.add(p5)
        assert p3.id in puzzle_ids
        assert p4.id in puzzle_ids
        assert p5.id not in puzzle_ids

    def _test_solve_puzzles(self):
        """
        Tests that puzzles can be submitted with the right solution
        """
        user_obj = new_user("c")
        d_user_obj = new_user("d")
        p = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), d_user_obj.id)
        data = {"user_id": user_obj.id,
                "puzzle_id": p.id,
                "complete_puzzle": json.dumps(self.sample_puzzle_solution)}
        resp = self.client.post("/sudoku/puzzle/", data=data)
        resp_dict = json.loads(resp.data)
        print resp_dict
        assert resp_dict["status"] == "ok"

    def _test_solve_wrong_puzzle(self):
        """
        Tests that bad solutions cannot be submitted
        """
        user_obj = new_user("c")
        d_user_obj = new_user("d")
        solution_copied = list(self.sample_puzzle_solution)
        solution_copied[0] = 3
        p = new_puzzle(json.dumps(self.sample_puzzle_solution), json.dumps(self.sample_puzzle), d_user_obj.id)
        data = {"user_id": user_obj.id,
                "puzzle_id": p.id,
                "complete_puzzle": json.dumps(solution_copied)}
        resp = self.client.post("/sudoku/puzzle/", data=data)
        resp_dict = json.loads(resp.data)
        assert resp_dict["status"] == "error"

    def _test_user_ranking(self):
        """
        Tests that ranking between users work.
        We test this by having a user that solves more puzzles than another,
        and ensures that this is true in the rankings
        """
        user_g_obj = new_user("g")
        user_e_obj = new_user("e")
        user_f_obj = new_user("f")
        completed_puzzle_json = json.dumps(self.sample_puzzle_solution)
        incompleted_puzzle_json = json.dumps(self.sample_puzzle)
        p1 = new_puzzle(completed_puzzle_json, incompleted_puzzle_json, user_g_obj.id)
        p2 = new_puzzle(completed_puzzle_json, incompleted_puzzle_json, user_g_obj.id)
        p3 = new_puzzle(completed_puzzle_json, incompleted_puzzle_json, user_g_obj.id)
        new_solution_record(user_e_obj.id, p1.id)
        new_solution_record(user_f_obj.id, p2.id)
        new_solution_record(user_f_obj.id, p3.id)
        resp = self.client.get("/user/ranks/")
        resp_dict = json.loads(resp.data)
        ranks_lis = resp_dict["rankings"]
        ranks = [(x['username'], x['rank']) for x in ranks_lis]
        assert (u"f", 0) in ranks
        assert (u"e", 1) in ranks

    def test_fail_min_puzzle_requirement(self):
        """
        Tests that a user who hasn't met the min requirement cannot parse the API
        """
        user_h_obj = new_user("h")
        data = {"user_id": user_h_obj.id}
        resp = self.client.get("/sudoku/puzzle/?" + urllib.urlencode(data))
        resp_dict = json.loads(resp.data)
        assert resp_dict["status"] == "error"