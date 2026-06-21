import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useCallback, useEffect } from "react";
import { Btn, Eyebrow, Panel, SectionTitle } from "@/components/ui-bits";
import { Upload, Video, Image as ImageIcon, Play, Pause, StopCircle, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// Upload endpoint:
// - Dev: relative path so the Vite proxy forwards it to FastAPI (avoids CORS).
// - Production: full Render backend URL via VITE_API_URL env var.
const UPLOAD_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/process/upload`
  : '/api/process/upload';


export const Route = createFileRoute("/demo")({
  head: () => ({ meta: [{ title: "Live Demo · GuardianEye" }] }),
  component: DemoPage,
});

interface ProcessingResult {
  id: string;
  timestamp: string;
  status: "processing" | "success" | "error";
  message: string;
  incident_id?: string;
  violations_detected?: number;
}

function DemoPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState<"image" | "video" | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingResults, setProcessingResults] = useState<ProcessingResult[]>([]);
  const [videoPlaying, setVideoPlaying] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  // Tracks the incident created by the first violating frame in a video session.
  // All subsequent frames from the same video append evidence to this incident.
  const videoIncidentIdRef = useRef<string | null>(null);
  // Use a ref for frameCount inside captureFrame to avoid stale closures.
  const frameCountRef = useRef(0);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
      toast.error("Please upload an image or video file");
      return;
    }

    // Determine file type
    const type = file.type.startsWith('image/') ? 'image' : 'video';
    
    // Create preview URL
    const url = URL.createObjectURL(file);
    
    setSelectedFile(file);
    setFileType(type);
    setPreviewUrl(url);
    setProcessingResults([]);
    setFrameCount(0);
    frameCountRef.current = 0;
    videoIncidentIdRef.current = null;   // reset per new file
    toast.success(`${type === 'image' ? 'Image' : 'Video'} loaded successfully`);
  };

  const addResult = (result: Omit<ProcessingResult, 'id' | 'timestamp'>) => {
    const newResult: ProcessingResult = {
      ...result,
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toLocaleTimeString(),
    };
    setProcessingResults(prev => [newResult, ...prev].slice(0, 50)); // Keep last 50 results
  };

  const processImage = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    // addResult({ status: "processing", message: "Uploading image..." });
    const processingId = Math.random().toString(36);

setProcessingResults(prev => [
  {
    id: processingId,
    timestamp: new Date().toLocaleTimeString(),
    status: "processing",
    message: "Uploading image..."
  },
  ...prev
]);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('camera_id', 'DEMO-IMG-001');
      formData.append('location', 'Demo Upload - Image');

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 130_000); // 130s matches backend limit

      const response = await fetch(UPLOAD_URL, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await response.json();

      if (data.success) {
       setProcessingResults(prev =>
  prev.map(r =>
    r.id === processingId
      ? {
          ...r,
          status: "success",
          message: `Detected: ${data.primary_violation || 'No violations'}`,
          incident_id: data.incident_id,
          violations_detected: data.violations_detected,
        }
      : r
  )
);
      } else {
        setProcessingResults(prev =>
  prev.map(r =>
    r.id === processingId
      ? { ...r, status: "error", message: data.message || "Processing failed" }
      : r
  )
);
        toast.error("Processing failed");
      }
    } catch (error) {
      const msg = error instanceof DOMException && error.name === 'AbortError'
        ? 'Request timed out — AI models are loading. Please retry in a moment.'
        : `Error: ${error}`;
      setProcessingResults(prev =>
  prev.map(r =>
    r.id === processingId
      ? { ...r, status: "error", message: msg }
      : r
  )
);
      toast.error("Upload failed. Make sure backend is running.");
    } finally {
      setIsProcessing(false);
    }
  };

  const captureFrame = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Video timestamp (seconds into the video)
    const videoTimestamp = video.currentTime;

    canvas.toBlob(async (blob) => {
      if (!blob) return;

      frameCountRef.current += 1;
      const currentFrame = frameCountRef.current;
      setFrameCount(currentFrame);

      const frameResultId = Math.random().toString(36);
      setProcessingResults(prev => [
        {
          id: frameResultId,
          timestamp: new Date().toLocaleTimeString(),
          status: "processing" as const,
          message: `Processing frame ${currentFrame} (t=${videoTimestamp.toFixed(1)}s)…`,
        },
        ...prev,
      ].slice(0, 50));

      try {
        const formData = new FormData();
        formData.append('file', blob, `frame_${currentFrame}.jpg`);
        formData.append('camera_id', 'DEMO-VID-001');
        formData.append('location', 'Demo Upload - Video');
        formData.append('timestamp_in_video', String(videoTimestamp));

        // If we already have an incident from this session, append to it
        const existingIncidentId = videoIncidentIdRef.current;
        if (existingIncidentId) {
          formData.append('incident_id', existingIncidentId);
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 130_000);
        const response = await fetch(UPLOAD_URL, { method: 'POST', body: formData, signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await response.json();

        if (data.success) {
          // Save the incident_id from the first frame that finds violations
          if (data.incident_id && !videoIncidentIdRef.current) {
            videoIncidentIdRef.current = data.incident_id;
          }

          const isAppend = !!existingIncidentId;
          setProcessingResults(prev =>
            prev.map(r =>
              r.id === frameResultId
                ? {
                    ...r,
                    status: "success" as const,
                    message: isAppend
                      ? `Frame ${currentFrame} (t=${videoTimestamp.toFixed(1)}s): evidence appended — ${data.primary_violation || 'no violations'}`
                      : `Frame ${currentFrame} (t=${videoTimestamp.toFixed(1)}s): ${data.primary_violation || 'no violations'}`,
                    incident_id: data.incident_id || existingIncidentId || undefined,
                    violations_detected: data.violations_detected,
                  }
                : r
            )
          );
        } else {
          setProcessingResults(prev =>
            prev.map(r =>
              r.id === frameResultId
                ? { ...r, status: "error" as const, message: `Frame ${currentFrame}: ${data.message}` }
                : r
            )
          );
        }
      } catch (error) {
        setProcessingResults(prev =>
          prev.map(r =>
            r.id === frameResultId
              ? { ...r, status: "error" as const, message: `Frame ${currentFrame}: upload failed` }
              : r
          )
        );
      }
    }, 'image/jpeg', 0.85);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startVideoProcessing = () => {
    if (!videoRef.current) return;
    setIsProcessing(true);
    setVideoPlaying(true);
    setFrameCount(0);
    frameCountRef.current = 0;
    videoIncidentIdRef.current = null;   // fresh incident for new session
    setProcessingResults([]);
    videoRef.current.play();
    // Capture a frame every 2 seconds (balance between coverage and server load)
    intervalRef.current = setInterval(captureFrame, 2000);
    toast.success("Video processing started — 1 frame every 2 s");
  };

  const stopVideoProcessing = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
    }
    setIsProcessing(false);
    setVideoPlaying(false);
    videoIncidentIdRef.current = null;   // reset so next video starts fresh
    frameCountRef.current = 0;
    toast.info(`Processing stopped. ${frameCount} frames processed.`);
  };

  const toggleVideoPlayback = () => {
    if (!videoRef.current) return;

    if (videoPlaying) {
      stopVideoProcessing();
    } else {
      startVideoProcessing();
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  return (
    <div className="p-5 lg:p-8 space-y-6">
      <SectionTitle
        eyebrow="Live demonstration · Upload & Process"
        title="Demo Mode"
        sub="Upload images or videos to simulate live camera feed. Videos are processed at 2 frames per second."
      />

      <div className="grid grid-cols-12 gap-6">
        {/* Upload Section */}
        <Panel className="col-span-12 lg:col-span-4">
          <Eyebrow>Step 1 · Upload</Eyebrow>
          <h3 className="font-display text-[22px] mt-2 mb-4">Select Media</h3>
          
          <label className="block">
            <input
              type="file"
              accept="image/*,video/*"
              onChange={handleFileSelect}
              className="hidden"
              disabled={isProcessing}
            />
            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-rust hover:bg-muted/20 transition-colors">
              <Upload className="size-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-[14px] font-medium">Click to upload</p>
              <p className="text-[12px] text-muted-foreground mt-1">
                Image (JPG, PNG) or Video (MP4, WebM)
              </p>
            </div>
          </label>

          {selectedFile && (
            <div className="mt-4 p-3 bg-muted rounded-md">
              <div className="flex items-center gap-2 text-[13px]">
                {fileType === 'image' ? (
                  <ImageIcon className="size-4 text-rust" />
                ) : (
                  <Video className="size-4 text-rust" />
                )}
                <span className="font-medium truncate">{selectedFile.name}</span>
              </div>
              <div className="text-[11px] text-muted-foreground mt-1">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB · {fileType}
              </div>
            </div>
          )}

          {selectedFile && !isProcessing && (
            <div className="mt-4 space-y-2">
              {fileType === 'image' ? (
                <Btn variant="primary" className="w-full" onClick={processImage}>
                  <ImageIcon className="size-4" /> Process Image
                </Btn>
              ) : (
                <Btn variant="primary" className="w-full" onClick={startVideoProcessing}>
                  <Play className="size-4" /> Start Video Processing
                </Btn>
              )}
            </div>
          )}

          {isProcessing && fileType === 'video' && (
            <div className="mt-4 space-y-2">
              <Btn variant="outline" className="w-full" onClick={toggleVideoPlayback}>
                {videoPlaying ? (
                  <><Pause className="size-4" /> Pause</>
                ) : (
                  <><Play className="size-4" /> Resume</>
                )}
              </Btn>
              <Btn variant="ghost" className="w-full" onClick={stopVideoProcessing}>
                <StopCircle className="size-4" /> Stop Processing
              </Btn>
            </div>
          )}

          {frameCount > 0 && (
            <div className="mt-4 p-3 bg-bone rounded-md">
              <div className="text-[12px] text-muted-foreground">Frames Processed</div>
              <div className="font-display text-[32px] leading-none mt-1">{frameCount}</div>
            </div>
          )}
        </Panel>

        {/* Preview Section */}
        <Panel className="col-span-12 lg:col-span-8">
          <Eyebrow>Step 2 · Preview</Eyebrow>
          <h3 className="font-display text-[22px] mt-2 mb-4">Media Preview</h3>

          {!previewUrl ? (
            <div className="aspect-video bg-muted rounded-lg flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Upload className="size-16 mx-auto mb-3 opacity-50" />
                <p className="text-[14px]">No media selected</p>
                <p className="text-[12px] mt-1">Upload an image or video to preview</p>
              </div>
            </div>
          ) : fileType === 'image' ? (
            <div className="aspect-video bg-ink rounded-lg overflow-hidden">
              <img src={previewUrl} alt="Preview" className="w-full h-full object-contain" />
            </div>
          ) : (
            <div className="aspect-video bg-ink rounded-lg overflow-hidden relative">
              <video
                ref={videoRef}
                src={previewUrl}
                className="w-full h-full object-contain"
                onEnded={stopVideoProcessing}
              />
              {isProcessing && (
                <div className="absolute top-4 right-4 bg-rust text-paper px-3 py-1.5 rounded-full text-[11px] font-mono uppercase tracking-wider flex items-center gap-2">
                  <div className="size-2 bg-paper rounded-full animate-pulse" />
                  Processing Live
                </div>
              )}
            </div>
          )}

          {/* Hidden canvas for frame extraction */}
          <canvas ref={canvasRef} className="hidden" />
        </Panel>

        {/* Results Section */}
        <Panel inset={false} className="col-span-12">
          <div className="p-5 pb-3 border-b border-border">
            <Eyebrow>Step 3 · Results</Eyebrow>
            <h3 className="font-display text-[22px] mt-2">Processing Log</h3>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {processingResults.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <Loader2 className="size-12 mx-auto mb-3 opacity-50" />
                <p className="text-[14px]">No processing results yet</p>
                <p className="text-[12px] mt-1">Upload and process media to see results</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {processingResults.map((result) => (
                  <div key={result.id} className="p-4 flex items-start gap-3 hover:bg-muted/40">
                    <div className="shrink-0 mt-0.5">
                      {result.status === 'processing' && (
                        <Loader2 className="size-4 text-rust animate-spin" />
                      )}
                      {result.status === 'success' && (
                        <CheckCircle2 className="size-4 text-moss" />
                      )}
                      {result.status === 'error' && (
                        <AlertTriangle className="size-4 text-rust" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium">{result.message}</span>
                        <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                          {result.timestamp}
                        </span>
                      </div>
                      {result.incident_id && (
                        <div className="text-[11px] text-muted-foreground mt-1">
                          Incident ID: {result.incident_id} · Violations: {result.violations_detected}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Panel>
      </div>

      {/* Info Panel */}
      <Panel>
        <Eyebrow>How it works</Eyebrow>
        <h3 className="font-display text-[22px] mt-2 mb-3">Demo Mode Explained</h3>
        <div className="space-y-3 text-[13.5px] leading-relaxed text-graphite">
          <p>
            <strong className="text-ink">Image Upload:</strong> Upload a traffic image. It will be sent to the AI model for analysis, 
            and any detected violations will be saved as incidents in the database.
          </p>
          <p>
            <strong className="text-ink">Video Upload:</strong> Upload a traffic video. The system extracts 2 frames per second (every 0.5s) 
            and processes each frame independently. This simulates a live CCTV feed analyzing traffic in real-time.
          </p>
          <p>
            <strong className="text-ink">Processing:</strong> Each frame/image goes through: Backend → AI Model (14 YOLOv8 models) 
            → Detection → MongoDB → Live Dashboard Update. Check the Violations page to see all detected incidents!
          </p>
        </div>
      </Panel>
    </div>
  );
}
