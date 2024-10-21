#!/bin/bash

# Get the directory of the script
script_dir="$(dirname "$(readlink -f "$0")")"

# Log file path
log_file="${script_dir}/cron_log.txt"

# List of folder paths (same as in the setup script)
folders=(
    "./Work"
    "./FailedPatients"
    "./HL7gen"
    "./Import"
    "./SentHL7"
    "./UnsentHL7"
    "./UploadedPatients"
    "./output"
)

# Cron frequency used in the setup script (weekly at midnight on Sunday)
cron_frequency="0 0 * * 0"

# Start logging
echo "---- Cron Removal Log $(date) ----" >> "$log_file"

# Backup current crontab
crontab -l > current_cron_jobs

# Remove cron jobs for each folder
for folder in "${folders[@]}"; do
    if [ -d "$folder" ]; then
        # Convert relative paths to absolute paths
        abs_folder=$(readlink -f "$folder")
        # Command pattern to look for in crontab
        cron_command="$cron_frequency rm -rf ${abs_folder}/*"
        
        # Remove the cron job matching this command
        sed -i "\|$cron_command|d" current_cron_jobs

        if grep -Fxq "$cron_command" current_cron_jobs; then
            echo "Failed to remove cron job for folder: $abs_folder" >> "$log_file"
        else
            echo "Removed cron job for folder: $abs_folder" >> "$log_file"
        fi
    else
        echo "Warning: Folder $folder does not exist." >> "$log_file"
    fi
done

# Install updated crontab
crontab current_cron_jobs

# Clean up temporary file
rm current_cron_jobs

# Log completion
echo "Cron jobs removed. See log for details." >> "$log_file"
echo "---------------------------------------" >> "$log_file"

# Remove the anacron job from /etc/anacrontab
anacron_task="7 5 weekly_cleanup /bin/bash ${script_dir}/add_clear_cron.sh"

if grep -Fxq "$anacron_task" /etc/anacrontab; then
    sudo sed -i "\|$anacron_task|d" /etc/anacrontab
    if grep -Fxq "$anacron_task" /etc/anacrontab; then
        echo "Failed to remove anacron task from /etc/anacrontab." >> "$log_file"
    else
        echo "Anacron task removed from /etc/anacrontab." >> "$log_file"
    fi
else
    echo "Anacron task not found in /etc/anacrontab." >> "$log_file"
fi

# Confirmation message for terminal
echo "Cleanup completed. Cron and anacron jobs removed. Log written to $log_file"
