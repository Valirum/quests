//go:build !unix

package schedule

import (
	"os/exec"
	"time"
)

func killTree(cmd *exec.Cmd) { cmd.WaitDelay = 2 * time.Second }
