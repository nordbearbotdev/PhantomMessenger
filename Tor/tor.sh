#!/bin/sh

trap 'kill -15 `cat tor.pid`' 15

tor --quiet -f torrc.txt --PidFile tor.pid &
wait
