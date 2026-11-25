// File: samples/sample5.ts
// Scenario: Document Scanner Component (Missing Information & Unbounded Streams)
// Author: 
// Ticket: 
// Target: 

import { Component, OnInit, ElementRef, ViewChild } from '@angular/core';

@Component({
  selector: 'app-document-scanner',
  standalone: true,
  template: `
    <div class="scanner-container">
      <video #preview autoplay playsinline></video>
      <button (click)="captureFrame()">Capture Document</button>
    </div>
  `
})
export class DocumentScannerComponent implements OnInit {
  @ViewChild('preview') previewElement!: ElementRef<HTMLVideoElement>;

  // Missing types: untyped any array
  capturedFrames: any[] = [];

  // Missing owner and target date in metadata above!

  ngOnInit(): void {
    // Architectural Blocker:
    // Starts hardware video stream with no error handler, no permission check,
    // and no fallback for browsers without WebRTC camera support
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
        this.previewElement.nativeElement.srcObject = stream;
      });
    // Missing: ngOnDestroy or DestroyRef.onDestroy to stop stream tracks!
    // Hardware camera will remain active and leak memory indefinitely after navigation.
  }

  captureFrame(): void {
    // Missing boundary checks and image compression pipeline
    this.capturedFrames.push({ timestamp: Date.now() });
  }
}
