# Batch Processing Feature

## Overview
The Medical Assistant now supports batch processing of multiple recordings, allowing users to process several recordings at once with the same settings.

## How to Use

1. **Select Multiple Recordings**:
   - In the Recordings tab, hold Ctrl (Windows/Linux) or Cmd (Mac) while clicking to select multiple recordings
   - Use Shift+Click to select a range of recordings

2. **Process Selected Recordings**:
   - Click the "Process Selected" button that appears in the second row of buttons
   - A dialog will appear with processing options

3. **Configure Processing Options**:
   - **Generate SOAP Notes**: Create SOAP notes from transcripts
   - **Generate Referrals**: Create referrals from SOAP notes
   - **Generate Letters**: Create letters from available content
   - **Processing Priority**: Choose Low, Normal, or High priority
   - **Skip existing content**: Avoid reprocessing recordings that already have the requested content
   - **Continue on errors**: Keep processing other recordings if one fails

4. **Monitor Progress**:
   - The status bar shows batch processing progress
   - Individual recording status is updated in the tree view
   - Notifications appear when processing completes

## Technical Details

### Components Modified

1. **UI Components**:
   - `workflow_ui.py`: Changed TreeView to allow multi-selection (`selectmode="extended"`)
   - Added "Process Selected" button and selection count display
   - Added batch processing dialog launcher

2. **Processing Queue**:
   - Added `add_batch_recordings()` method for batch submission
   - Added batch tracking with `batch_id`
   - Added batch completion callbacks
   - Added document generation methods for SOAP, referral, and letter creation

3. **Database**:
   - Added `get_recordings_by_ids()` method for bulk fetching
   - Added migration (version 8) for batch processing support

4. **Document Generators**:
   - Added `process_batch_recordings()` method
   - Integrated with processing queue for batch operations

### Database Schema Changes

Migration 8 adds:
- `batch_id` column to `processing_queue` table
- `batch_processing` table for batch metadata
- Indexes for efficient batch queries

### Processing Flow

1. User selects recordings and clicks "Process Selected"
2. BatchProcessingDialog collects processing options
3. DocumentGenerators.process_batch_recordings() prepares batch data
4. ProcessingQueue.add_batch_recordings() queues all recordings
5. Each recording is processed based on options
6. Progress updates are sent via callbacks
7. UI is refreshed when batch completes

### Error Handling

- Individual recording failures don't stop the batch (if "continue on error" is enabled)
- Failed recordings are tracked and reported in the completion summary
- Retry logic applies to individual recordings within the batch

## Future Enhancements

- Select All/Deselect All buttons
- Batch export functionality
- Progress dialog with detailed status
- Batch processing templates for common workflows
- Queue prioritization for batch vs individual processing