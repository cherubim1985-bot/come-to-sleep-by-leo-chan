import Cocoa
import CoreGraphics
import Foundation

func post(_ type: CGEventType, x: Double, y: Double, clickState: Int64 = 1) {
    let point = CGPoint(x: x, y: y)
    guard let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left) else {
        fputs("failed to create mouse event\n", stderr)
        exit(1)
    }
    event.setIntegerValueField(.mouseEventClickState, value: clickState)
    event.post(tap: .cghidEventTap)
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("usage: click_at.swift <x> <y> [double]\n", stderr)
    exit(2)
}

guard let x = Double(args[1]), let y = Double(args[2]) else {
    fputs("x/y must be numbers\n", stderr)
    exit(2)
}

let isDouble = args.count >= 4 && args[3].lowercased() == "double"

post(.mouseMoved, x: x, y: y)
usleep(80_000)
post(.leftMouseDown, x: x, y: y, clickState: isDouble ? 2 : 1)
usleep(40_000)
post(.leftMouseUp, x: x, y: y, clickState: isDouble ? 2 : 1)

if isDouble {
    usleep(120_000)
    post(.leftMouseDown, x: x, y: y, clickState: 2)
    usleep(40_000)
    post(.leftMouseUp, x: x, y: y, clickState: 2)
}

print("clicked \(x),\(y)\(isDouble ? " double" : "")")
