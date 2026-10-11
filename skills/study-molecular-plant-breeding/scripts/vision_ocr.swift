// Offline Chinese + English page OCR using macOS Vision. No book text bundled.
import Foundation
import Vision

if CommandLine.arguments.count != 2 {
    fputs("Usage: vision-ocr /path/to/page.png\n", stderr)
    exit(2)
}
do {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
    try handler.perform([request])
    let text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    print(text.joined(separator: "\n"))
} catch {
    fputs("Vision OCR failed: \(error)\n", stderr)
    exit(2)
}
