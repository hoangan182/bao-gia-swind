import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    print("Usage: ocr_vision_bbox <image_path>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: imagePath)

guard let image = NSImage(contentsOf: url),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERROR: Failed to load image at \(imagePath)")
    exit(1)
}

let request = VNRecognizeTextRequest { request, error in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    for obs in observations {
        if let top = obs.topCandidates(1).first {
            let bbox = obs.boundingBox
            // bbox: origin at bottom-left in Vision (0..1, 0..1)
            print(String(format: "%.4f,%.4f,%.4f,%.4f\t%@", bbox.origin.x, bbox.origin.y, bbox.size.width, bbox.size.height, top.string))
        }
    }
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["vi-VN", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    print("ERROR: \(error)")
    exit(1)
}
