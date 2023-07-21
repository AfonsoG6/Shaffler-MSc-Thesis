package utils

import (
	"io"
	"net"
	"time"
)

func CopyWithTimeout(copyTimeout time.Duration, dst, src net.Conn) (int64, error) {
	buf := make([]byte, 1024)
	var totalBytesCopied int64

	for {
		// Reset the deadlines before each read operation
		err := SetDeadlines(copyTimeout, src, dst)
		if err != nil {
			return totalBytesCopied, err
		}

		n, readErr := src.Read(buf)
		if readErr != nil {
			return totalBytesCopied, readErr
		}

		// Reset the deadlines before each write operation
		err = SetDeadlines(copyTimeout, src, dst)
		if err != nil {
			return totalBytesCopied, err
		}

		bytesWritten, writeErr := writeAll(dst, buf[:n])
		if writeErr != nil {
			return totalBytesCopied, writeErr
		}

		totalBytesCopied += int64(bytesWritten)
	}
}

func writeAll(dst io.Writer, src []byte) (int, error) {
	totalBytesWritten := 0
	lenSrc := len(src)
	for totalBytesWritten < lenSrc {
		n, err := dst.Write(src[totalBytesWritten:])
		if err != nil {
			return totalBytesWritten, err
		}
		totalBytesWritten += n
	}

	return totalBytesWritten, nil
}
