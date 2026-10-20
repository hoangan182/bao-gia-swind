document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('runStage2Btn') || document.getElementById('runAgentsBtn');
    const executionPanel = document.getElementById('executionPanel');
    const dropZone = document.getElementById('dropZone');
    const uploadedFile = document.getElementById('uploadedFile');

    // Handle Drag & Drop Fake UI
    if (dropZone && uploadedFile) {
        dropZone.addEventListener('click', (e) => {
            if(e.target.tagName !== 'BUTTON') return;
            var h4 = dropZone.querySelector('h4');
            var p = dropZone.querySelector('p');
            var btn = dropZone.querySelector('button');
            var icon = dropZone.querySelector('.upload-icon');
            if (h4) h4.style.display = 'none';
            if (p) p.style.display = 'none';
            if (btn) btn.style.display = 'none';
            if (icon) icon.style.display = 'none';
            uploadedFile.classList.remove('hide');
            dropZone.style.padding = '2rem';
            dropZone.style.borderStyle = 'solid';
            dropZone.style.borderColor = '#10b981';
            dropZone.style.background = '#f0fdf4';
        });
    }

    // Handle Execution Action
    if (runBtn && executionPanel) {
        runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> HỆ THỐNG ĐANG CHẠY BÓC TÁCH...';
        runBtn.disabled = true;
        runBtn.style.opacity = '0.8';
        
        executionPanel.classList.remove('hide');
        
        // Simulate Agent steps
        setTimeout(() => {
            const items = document.querySelectorAll('.timeline-item');
            
            // Move from Agent 1 to Agent 2
            items[1].classList.remove('active');
            items[1].classList.add('done');
            items[1].querySelector('.marker').innerHTML = '<i class="fa-solid fa-check"></i>';
            items[1].querySelector('p').textContent = 'Hoàn thành bóc tách 605 dòng (2,587 cấu kiện). Đã sinh file nháp.';
            
            items[2].classList.remove('pending');
            items[2].classList.add('active');
            items[2].querySelector('.marker').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            items[2].querySelector('p').textContent = 'Đang rà soát lỗ hổng kỹ thuật và toán học...';
            
            setTimeout(() => {
                // Agent 2 Done
                items[2].classList.remove('active');
                items[2].classList.add('done');
                items[2].querySelector('.marker').innerHTML = '<i class="fa-solid fa-check"></i>';
                items[2].querySelector('h4').textContent = 'Agent 2 (Checker) - QA_PASSED';
                items[2].querySelector('p').textContent = 'Không phát hiện lỗi. Đã xuất xưởng BANA_HILLS_ESTIMATION_VERIFIED.xlsx';
                
                runBtn.innerHTML = '<i class="fa-solid fa-download"></i> TẢI FILE EXCEL BÁO GIÁ';
                runBtn.disabled = false;
                runBtn.classList.replace('btn-primary', 'btn-success');
                runBtn.style.background = '#10b981';
                
            }, 2500);
            
        }, 3000);
    });
});
