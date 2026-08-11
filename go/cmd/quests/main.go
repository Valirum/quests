package main

import (
	"os"

	"github.com/valirum/quests/go/internal/cli"
)

func main() {
	os.Exit(cli.Run(os.Args[1:]))
}
