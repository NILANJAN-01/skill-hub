#!/bin/sh
robot --include SMOKEORREGRESSION --exclude "slow&flaky" --outputdir results tests
testdoc tests testdoc.html
robot --include "smoke OR regression" --exclude smokeORregression tests
