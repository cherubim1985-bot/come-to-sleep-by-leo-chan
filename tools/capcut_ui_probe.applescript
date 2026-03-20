on safeValue(exprResult)
	if exprResult is missing value then
		return ""
	end if
	return exprResult as text
end safeValue

on safeList(exprResult)
	try
		if exprResult is missing value then
			return {}
		end if
		return exprResult
	on error
		return {}
	end try
end safeList

on run
	tell application "CapCut" to activate
	delay 2
	
	set outputLines to {}
	
	tell application "System Events"
		tell process "CapCut"
			set frontmost to true
			set windowCount to count of windows
			copy ("window_count=" & windowCount) to end of outputLines
			
			repeat with i from 1 to windowCount
				try
					set theWindow to window i
					set windowName to my safeValue(name of theWindow)
					set buttonNames to my safeList(name of every button of theWindow)
					set staticTexts to my safeList(value of every static text of theWindow)
					copy ("window_" & i & "_name=" & windowName) to end of outputLines
					copy ("window_" & i & "_buttons=" & buttonNames as text) to end of outputLines
					copy ("window_" & i & "_texts=" & staticTexts as text) to end of outputLines
				on error errMsg number errNum
					copy ("window_" & i & "_error=" & errNum & ":" & errMsg) to end of outputLines
				end try
			end repeat
		end tell
	end tell
	
	return outputLines as text
end run
