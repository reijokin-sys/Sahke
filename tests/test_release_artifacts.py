#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseArtifactTest(unittest.TestCase):
    def test_build_does_not_delete_the_dist_archive(self):
        build = (ROOT / "tools/build.sh").read_text()
        self.assertNotIn('rm -rf "$PROJECT/dist"', build)
        self.assertIn('Kohdepaketti on jo olemassa', build)


if __name__ == "__main__":
    unittest.main()
