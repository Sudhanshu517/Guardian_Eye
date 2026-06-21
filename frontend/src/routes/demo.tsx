import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef, useCallback, useEffect } from "react";
import { Btn, Eyebrow, Panel, SectionTitle } from "@/components/ui-bits";
import { Upload, Video, Image as ImageIcon, Play, Pause, StopCircle, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// Upload endpoint — relative path so the Vite dev proxy forwards it to
// FastAPI (localhost:8000) as same-origin. This avoids CORS preflight and
// prevents the Nitro dev server from intercepting the multipart response.
// In production the same relative path is served by whatever reverse proxy
// sits in front (Nginx / Cloudflare / Railway), so no change needed there.
const UPLOAD_URL = '/api/process/upload';

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
    addResult({ status: "processing", message: "Uploading image..." });

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
        addResult({
          status: "success",
          message: `Detected: ${data.primary_violation || 'No violations'}`,
          incident_id: data.incident_id,
          violations_detected: data.violations_detected,
        });
        toast.success("Image processed successfully!");
      } else {
        addResult({
          status: "error",
          message: data.message || "Processing failed",
        });
        toast.error("Processing failed");
      }
    } catch (error) {
      const msg = error instanceof DOMException && error.name === 'AbortError'
        ? 'Request timed out — AI models are loading. Please retry in a moment.'
        : `Error: ${error}`;
      addResult({
        status: "error",
        message: msg,
      });
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

    // Set canvas size to video size
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw current video frame to canvas
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert canvas to blob
    canvas.toBlob(async (blob) => {
      if (!blob) return;

      const currentFrame = frameCount + 1;
      setFrameCount(currentFrame);

      addResult({
        status: "processing",
        message: `Processing frame ${currentFrame}...`,
      });

      try {
        const formData = new FormData();
        formData.append('file', blob, `frame_${currentFrame}.jpg`);
        formData.append('camera_id', `DEMO-VID-${currentFrame}`);
        formData.append('location', `Demo Upload - Video Frame ${currentFrame}`);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 130_000);

        const response = await fetch(UPLOAD_URL, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        const data = await response.json();

        if (data.success) {
          addResult({
            status: "success",
            message: `Frame ${currentFrame}: ${data.primary_violation || 'No violations'} (${data.violations_detected} total)`,
            incident_id: data.incident_id,
            violations_detected: data.violations_detected,
          });
        } else {
          addResult({
            status: "error",
            message: `Frame ${currentFrame}: ${data.message}`,
          });
        }
      } catch (error) {
        addResult({
          status: "error",
          message: `Frame ${currentFrame}: Upload failed`,
        });
      }
    }, 'image/jpeg', 0.8);
  }, [frameCount]);

  const startVideoProcessing = () => {
    if (!videoRef.current) return;

    setIsProcessing(true);
    setVideoPlaying(true);
    setFrameCount(0);
    setProcessingResults([]);
    
    videoRef.current.play();
    
    // Capture frame every 0.5 seconds (2 frames per second)
    intervalRef.current = setInterval(captureFrame, 500);
    
    toast.success("Video processing started - 2 frames/second");
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
