#!/bin/sh

function changelog() {
	git log --date=short --pretty="%ad%n %s%n" | head -n -1
}
