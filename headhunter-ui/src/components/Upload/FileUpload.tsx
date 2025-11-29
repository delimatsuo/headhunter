import React, { useState, useRef } from 'react';
import { apiService } from '../../services/api';
import { UploadProgress } from '../../types';

interface FileUploadProps {
  candidateId: string;
  onUploadComplete?: (fileUrl: string) => void;
  onUploadError?: (error: string) => void;
  acceptedTypes?: string[];
  maxSize?: number; // in MB
  className?: string;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  candidateId,
  onUploadComplete,
  onUploadError,
  acceptedTypes = ['.pdf', '.doc', '.docx', '.txt'],
  maxSize = 10,
  className = ''
}) => {
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({
    progress: 0,
    status: 'idle'
  });
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    // Check file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > maxSize) {
      return `File size must be less than ${maxSize}MB`;
    }

    // Check file type
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!acceptedTypes.includes(fileExtension)) {
      return `File type not supported. Accepted types: ${acceptedTypes.join(', ')}`;
    }

    return null;
  };

  const uploadFile = async (file: File) => {
    setUploadProgress({ progress: 0, status: 'uploading' });

    try {
      // Generate upload URL
      const uploadUrlResult = await apiService.generateUploadUrl(
        candidateId,
        file.name,
        file.type || 'application/octet-stream',
        file.size
      );

      if (!uploadUrlResult.success || !uploadUrlResult.data) {
        throw new Error(uploadUrlResult.error || 'Failed to generate upload URL');
      }

      const { uploadUrl, fileUrl, uploadSessionId, requiredHeaders } = uploadUrlResult.data;

      // Upload file with progress tracking
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = (event.loaded / event.total) * 100;
          setUploadProgress({ progress, status: 'uploading' });
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          setUploadProgress({ progress: 100, status: 'completed' });
          onUploadComplete?.(fileUrl);
        } else {
          const error = `Upload failed: ${xhr.statusText}`;
          setUploadProgress({ progress: 0, status: 'error', error });
          onUploadError?.(error);
        }
      });

      xhr.addEventListener('error', () => {
        const error = 'Upload failed: Network error';
        setUploadProgress({ progress: 0, status: 'error', error });
        onUploadError?.(error);
      });

      xhr.open('PUT', uploadUrl);
      xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
      xhr.send(file);
    } catch (error: any) {
      const errorMessage = error.message || 'Upload failed';
      setUploadProgress({ progress: 0, status: 'error', error: errorMessage });
      onUploadError?.(errorMessage);
    }
  };

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    const validationError = validateFile(file);

    if (validationError) {
      setUploadProgress({ progress: 0, status: 'error', error: validationError });
      onUploadError?.(validationError);
      return;
    }

    await uploadFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const resetUpload = () => {
    setUploadProgress({ progress: 0, status: 'idle' });
  };

  return (
    <div className={`file-upload ${className}`}>
      <div
        className={`upload-area ${dragActive ? 'drag-active' : ''
          } ${uploadProgress.status === 'uploading' ? 'uploading' : ''
          } ${uploadProgress.status === 'error' ? 'error' : ''
          } ${uploadProgress.status === 'completed' ? 'completed' : ''
          }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptedTypes.join(',')}
          onChange={(e) => handleFileSelect(e.target.files)}
          style={{ display: 'none' }}
        />

        {uploadProgress.status === 'idle' && (
          <div className="upload-prompt">
            <div className="upload-icon">📄</div>
            <h3>Upload Resume</h3>
            <p>Drag and drop your resume here, or click to browse</p>
            <p className="file-info">
              Supported formats: {acceptedTypes.join(', ')}
            </p>
            <p className="file-info">
              Max size: {maxSize}MB
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleButtonClick}
            >
              Choose File
            </button>
          </div>
        )}

        {uploadProgress.status === 'uploading' && (
          <div className="upload-progress">
            <div className="upload-icon">⬆️</div>
            <h3>Uploading...</h3>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${uploadProgress.progress}%` }}
              ></div>
            </div>
            <p>{Math.round(uploadProgress.progress)}% complete</p>
          </div>
        )}

        {uploadProgress.status === 'completed' && (
          <div className="upload-success">
            <div className="upload-icon">✅</div>
            <h3>Upload Complete!</h3>
            <p>Your resume has been uploaded successfully</p>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={resetUpload}
            >
              Upload Another
            </button>
          </div>
        )}

        {uploadProgress.status === 'error' && (
          <div className="upload-error">
            <div className="upload-icon">❌</div>
            <h3>Upload Failed</h3>
            <p>{uploadProgress.error}</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={resetUpload}
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
};