"""
PDF Export Functionality

This module provides PDF generation and export capabilities for medical documents
including SOAP notes, referral letters, diagnostic reports, medication analyses,
and other clinical documentation.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import tempfile

from utils.structured_logging import get_logger

logger = get_logger(__name__)

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas


class PDFExporter:
    """Handles PDF generation for medical documents with professional formatting."""
    
    def __init__(self, page_size=letter):
        """Initialize PDF exporter with default settings.
        
        Args:
            page_size: Page size (default: letter, can be A4)
        """
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Default margins
        self.left_margin = 0.75 * inch
        self.right_margin = 0.75 * inch
        self.top_margin = 1 * inch
        self.bottom_margin = 0.75 * inch
        
        # Header/footer settings
        self.include_header = True
        self.include_footer = True
        self.header_text = "Medical Assistant Report"
        self.footer_text = None
        
        # Optional logo path
        self.logo_path = None
        self.logo_height = 0.5 * inch

        # Simple letterhead settings
        self.clinic_name = ""
        self.doctor_name = ""
        
    def _setup_custom_styles(self):
        """Set up custom paragraph styles for medical documents."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#4a4a4a'),
            spaceAfter=6,
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=12,
            spaceAfter=6,
            leftIndent=0,
            bold=True
        ))
        
        # Content style
        self.styles.add(ParagraphStyle(
            name='ContentNormal',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#333333'),
            alignment=TA_JUSTIFY
        ))
        
        # Medication style
        self.styles.add(ParagraphStyle(
            name='MedicationItem',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            bulletIndent=10,
            textColor=colors.HexColor('#2c3e50')
        ))
        
        # Warning style
        self.styles.add(ParagraphStyle(
            name='Warning',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#e74c3c'),
            backColor=colors.HexColor('#ffebee'),
            borderColor=colors.HexColor('#e74c3c'),
            borderWidth=1,
            borderPadding=4,
            leftIndent=10,
            rightIndent=10
        ))
        
    def _create_header_footer(self, canvas, doc):
        """Add header and footer to each page.

        Args:
            canvas: ReportLab canvas object
            doc: Document template object
        """
        canvas.saveState()

        # Header
        if self.include_header:
            header_y_offset = 0

            # Simple letterhead (clinic name + doctor name)
            if self.clinic_name or self.doctor_name:
                center_x = doc.width / 2 + doc.leftMargin

                if self.clinic_name:
                    canvas.setFont('Helvetica-Bold', 14)
                    canvas.setFillColor(colors.HexColor('#1a1a1a'))
                    canvas.drawCentredString(
                        center_x,
                        doc.height + doc.topMargin - 15,
                        self.clinic_name
                    )
                    header_y_offset = 18

                if self.doctor_name:
                    canvas.setFont('Helvetica', 11)
                    canvas.setFillColor(colors.HexColor('#4a4a4a'))
                    canvas.drawCentredString(
                        center_x,
                        doc.height + doc.topMargin - 15 - header_y_offset,
                        self.doctor_name
                    )
                    header_y_offset += 15

                # Letterhead separator line
                canvas.setStrokeColor(colors.HexColor('#999999'))
                canvas.line(
                    doc.leftMargin,
                    doc.height + doc.topMargin - 20 - header_y_offset,
                    doc.width + doc.leftMargin,
                    doc.height + doc.topMargin - 20 - header_y_offset
                )

            elif self.logo_path and os.path.exists(self.logo_path):
                # Draw logo (if no simple letterhead)
                canvas.drawImage(
                    self.logo_path,
                    doc.leftMargin,
                    doc.height + doc.topMargin - self.logo_height,
                    height=self.logo_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )

                # Header text
                canvas.setFont('Helvetica', 10)
                canvas.setFillColor(colors.HexColor('#666666'))
                canvas.drawRightString(
                    doc.width + doc.leftMargin,
                    doc.height + doc.topMargin - 20,
                    self.header_text
                )

                # Header line
                canvas.setStrokeColor(colors.HexColor('#cccccc'))
                canvas.line(
                    doc.leftMargin,
                    doc.height + doc.topMargin - 30,
                    doc.width + doc.leftMargin,
                    doc.height + doc.topMargin - 30
                )
            else:
                # Default header text only
                canvas.setFont('Helvetica', 10)
                canvas.setFillColor(colors.HexColor('#666666'))
                canvas.drawRightString(
                    doc.width + doc.leftMargin,
                    doc.height + doc.topMargin - 20,
                    self.header_text
                )

                # Header line
                canvas.setStrokeColor(colors.HexColor('#cccccc'))
                canvas.line(
                    doc.leftMargin,
                    doc.height + doc.topMargin - 30,
                    doc.width + doc.leftMargin,
                    doc.height + doc.topMargin - 30
                )
        
        # Footer
        if self.include_footer:
            # Footer line
            canvas.setStrokeColor(colors.HexColor('#cccccc'))
            canvas.line(
                doc.leftMargin,
                doc.bottomMargin + 20,
                doc.width + doc.leftMargin,
                doc.bottomMargin + 20
            )
            
            # Page number
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.HexColor('#666666'))
            page_num = f"Page {doc.page}"
            canvas.drawString(
                doc.leftMargin,
                doc.bottomMargin,
                page_num
            )
            
            # Date
            date_str = datetime.now().strftime("%B %d, %Y")
            canvas.drawCentredString(
                doc.width / 2 + doc.leftMargin,
                doc.bottomMargin,
                date_str
            )
            
            # Footer text (if provided)
            if self.footer_text:
                canvas.drawRightString(
                    doc.width + doc.leftMargin,
                    doc.bottomMargin,
                    self.footer_text
                )
        
        canvas.restoreState()
    
    def generate_soap_note_pdf(self, soap_data: Dict[str, Any], output_path: str,
                              patient_info: Optional[Dict[str, Any]] = None) -> bool:
        """Generate PDF for SOAP note.
        
        Args:
            soap_data: Dictionary containing SOAP sections
            output_path: Path to save the PDF
            patient_info: Optional patient information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            story.append(Paragraph("SOAP Note", self.styles['CustomTitle']))
            
            # Patient info if provided
            if patient_info:
                patient_text = f"Patient: {patient_info.get('name', 'N/A')}"
                if patient_info.get('dob'):
                    patient_text += f" | DOB: {patient_info['dob']}"
                if patient_info.get('mrn'):
                    patient_text += f" | MRN: {patient_info['mrn']}"
                story.append(Paragraph(patient_text, self.styles['CustomSubtitle']))
                story.append(Spacer(1, 0.3 * inch))
            
            # SOAP sections
            sections = [
                ('Subjective', soap_data.get('subjective', '')),
                ('Objective', soap_data.get('objective', '')),
                ('Assessment', soap_data.get('assessment', '')),
                ('Plan', soap_data.get('plan', ''))
            ]
            
            for section_name, content in sections:
                if content:
                    story.append(Paragraph(section_name, self.styles['SectionHeader']))
                    story.append(Paragraph(content, self.styles['ContentNormal']))
                    story.append(Spacer(1, 0.2 * inch))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated SOAP note PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating SOAP note PDF: {str(e)}")
            return False
    
    def generate_medication_report_pdf(self, medication_data: Dict[str, Any],
                                      output_path: str,
                                      report_type: str = "comprehensive") -> bool:
        """Generate PDF for medication analysis report.
        
        Args:
            medication_data: Dictionary containing medication analysis
            output_path: Path to save the PDF
            report_type: Type of report (comprehensive, interactions, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            title = f"Medication {report_type.title()} Report"
            story.append(Paragraph(title, self.styles['CustomTitle']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Medications list
            if medication_data.get('medications'):
                story.append(Paragraph("Medications", self.styles['SectionHeader']))
                for med in medication_data['medications']:
                    med_text = f"• {med['name']}"
                    if med.get('dosage'):
                        med_text += f" - {med['dosage']}"
                    if med.get('frequency'):
                        med_text += f" ({med['frequency']})"
                    story.append(Paragraph(med_text, self.styles['MedicationItem']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Interactions
            if medication_data.get('interactions'):
                story.append(Paragraph("Drug Interactions", self.styles['SectionHeader']))
                
                # Create interactions table
                interaction_data = [['Drug 1', 'Drug 2', 'Severity', 'Description']]
                for interaction in medication_data['interactions']:
                    interaction_data.append([
                        interaction.get('drug1', ''),
                        interaction.get('drug2', ''),
                        interaction.get('severity', ''),
                        interaction.get('description', '')[:50] + '...'
                    ])
                
                interaction_table = Table(interaction_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 2.5*inch])
                interaction_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(interaction_table)
                story.append(Spacer(1, 0.2 * inch))
            
            # Warnings
            if medication_data.get('warnings'):
                story.append(Paragraph("Warnings", self.styles['SectionHeader']))
                for warning in medication_data['warnings']:
                    story.append(Paragraph(f"⚠️ {warning}", self.styles['Warning']))
                    story.append(Spacer(1, 0.1 * inch))
            
            # Recommendations
            if medication_data.get('recommendations'):
                story.append(Paragraph("Recommendations", self.styles['SectionHeader']))
                story.append(Paragraph(medication_data['recommendations'], 
                                     self.styles['ContentNormal']))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated medication report PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating medication report PDF: {str(e)}")
            return False
    
    def generate_diagnostic_report_pdf(self, diagnostic_data: Dict[str, Any],
                                      output_path: str) -> bool:
        """Generate PDF for diagnostic analysis report.
        
        Args:
            diagnostic_data: Dictionary containing diagnostic analysis
            output_path: Path to save the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            story.append(Paragraph("Diagnostic Analysis Report", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Clinical findings
            if diagnostic_data.get('clinical_findings'):
                story.append(Paragraph("Clinical Findings", self.styles['SectionHeader']))
                story.append(Paragraph(diagnostic_data['clinical_findings'], 
                                     self.styles['ContentNormal']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Differential diagnoses
            if diagnostic_data.get('differentials'):
                story.append(Paragraph("Differential Diagnoses", self.styles['SectionHeader']))
                
                for i, diff in enumerate(diagnostic_data['differentials'], 1):
                    # Diagnosis name and probability
                    diff_text = f"{i}. {diff['diagnosis']}"
                    if diff.get('probability'):
                        diff_text += f" ({diff['probability']})"
                    story.append(Paragraph(diff_text, self.styles['Heading3']))
                    
                    # Supporting evidence
                    if diff.get('evidence'):
                        story.append(Paragraph("Supporting Evidence:", self.styles['Normal']))
                        for evidence in diff['evidence']:
                            story.append(Paragraph(f"• {evidence}", self.styles['MedicationItem']))
                    
                    # Recommended tests
                    if diff.get('tests'):
                        story.append(Paragraph("Recommended Tests:", self.styles['Normal']))
                        for test in diff['tests']:
                            story.append(Paragraph(f"• {test}", self.styles['MedicationItem']))
                    
                    story.append(Spacer(1, 0.15 * inch))
            
            # Red flags
            if diagnostic_data.get('red_flags'):
                story.append(Paragraph("Red Flags", self.styles['SectionHeader']))
                for flag in diagnostic_data['red_flags']:
                    story.append(Paragraph(f"🚨 {flag}", self.styles['Warning']))
                    story.append(Spacer(1, 0.1 * inch))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated diagnostic report PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating diagnostic report PDF: {str(e)}")
            return False
    
    def generate_referral_letter_pdf(self, referral_data: Dict[str, Any],
                                    output_path: str,
                                    sender_info: Optional[Dict[str, Any]] = None,
                                    recipient_info: Optional[Dict[str, Any]] = None) -> bool:
        """Generate PDF for referral letter.
        
        Args:
            referral_data: Dictionary containing referral content
            output_path: Path to save the PDF
            sender_info: Optional sender/clinic information
            recipient_info: Optional recipient information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Sender info (clinic letterhead)
            if sender_info:
                story.append(Paragraph(sender_info.get('clinic_name', 'Medical Clinic'),
                                     self.styles['CustomTitle']))
                if sender_info.get('address'):
                    story.append(Paragraph(sender_info['address'], 
                                         self.styles['CustomSubtitle']))
                if sender_info.get('phone'):
                    story.append(Paragraph(f"Tel: {sender_info['phone']}", 
                                         self.styles['CustomSubtitle']))
                story.append(Spacer(1, 0.3 * inch))
            
            # Date
            story.append(Paragraph(datetime.now().strftime("%B %d, %Y"), 
                                 self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
            
            # Recipient info
            if recipient_info:
                story.append(Paragraph(recipient_info.get('name', 'To Whom It May Concern'),
                                     self.styles['Normal']))
                if recipient_info.get('title'):
                    story.append(Paragraph(recipient_info['title'], self.styles['Normal']))
                if recipient_info.get('address'):
                    story.append(Paragraph(recipient_info['address'], self.styles['Normal']))
                story.append(Spacer(1, 0.3 * inch))
            
            # Subject line
            if referral_data.get('subject'):
                story.append(Paragraph(f"Re: {referral_data['subject']}", 
                                     self.styles['Heading3']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Salutation
            salutation = "Dear " + recipient_info.get('name', 'Colleague') if recipient_info else "Dear Colleague"
            story.append(Paragraph(salutation + ",", self.styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
            
            # Letter body
            if referral_data.get('body'):
                # Split body into paragraphs
                paragraphs = referral_data['body'].split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        story.append(Paragraph(para, self.styles['ContentNormal']))
                        story.append(Spacer(1, 0.1 * inch))
            
            # Closing
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("Sincerely,", self.styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Signature line
            if sender_info and sender_info.get('doctor_name'):
                story.append(Paragraph(sender_info['doctor_name'], self.styles['Normal']))
                if sender_info.get('doctor_title'):
                    story.append(Paragraph(sender_info['doctor_title'], self.styles['Normal']))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated referral letter PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating referral letter PDF: {str(e)}")
            return False
    
    def generate_workflow_report_pdf(self, workflow_data: Dict[str, Any],
                                    output_path: str) -> bool:
        """Generate PDF for clinical workflow.
        
        Args:
            workflow_data: Dictionary containing workflow steps and progress
            output_path: Path to save the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            workflow_type = workflow_data.get('workflow_type', 'Clinical').replace('_', ' ').title()
            story.append(Paragraph(f"{workflow_type} Workflow", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Patient info if available
            if workflow_data.get('patient_info'):
                patient = workflow_data['patient_info']
                patient_text = f"Patient: {patient.get('name', 'N/A')}"
                if patient.get('primary_concern'):
                    patient_text += f" | Concern: {patient['primary_concern']}"
                story.append(Paragraph(patient_text, self.styles['CustomSubtitle']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Workflow steps
            if workflow_data.get('steps'):
                story.append(Paragraph("Workflow Steps", self.styles['SectionHeader']))
                
                # Create checklist table
                checklist_data = []
                for i, step in enumerate(workflow_data['steps'], 1):
                    status = "☑" if step.get('completed') else "☐"
                    step_text = f"{i}. {step['description']}"
                    time_est = step.get('time_estimate', '')
                    checklist_data.append([status, step_text, time_est])
                
                checklist_table = Table(checklist_data, 
                                      colWidths=[0.3*inch, 5*inch, 1*inch])
                checklist_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                    ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6)
                ]))
                story.append(checklist_table)
                story.append(Spacer(1, 0.2 * inch))
            
            # Notes section
            if workflow_data.get('notes'):
                story.append(Paragraph("Notes", self.styles['SectionHeader']))
                story.append(Paragraph(workflow_data['notes'], self.styles['ContentNormal']))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated workflow report PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating workflow report PDF: {str(e)}")
            return False
    
    def generate_data_extraction_report_pdf(self, extraction_data: Dict[str, Any],
                                           output_path: str,
                                           format_type: str = "structured") -> bool:
        """Generate PDF for extracted clinical data.
        
        Args:
            extraction_data: Dictionary containing extracted data
            output_path: Path to save the PDF
            format_type: Format type (structured, table, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            story.append(Paragraph("Clinical Data Extraction Report", 
                                 self.styles['CustomTitle']))
            story.append(Spacer(1, 0.3 * inch))
            
            # Vitals
            if extraction_data.get('vitals'):
                story.append(Paragraph("Vital Signs", self.styles['SectionHeader']))
                vitals_data = [['Parameter', 'Value', 'Unit', 'Status']]
                for vital in extraction_data['vitals']:
                    vitals_data.append([
                        vital.get('name', ''),
                        vital.get('value', ''),
                        vital.get('unit', ''),
                        vital.get('status', 'Normal')
                    ])
                
                vitals_table = Table(vitals_data, 
                                   colWidths=[2*inch, 1*inch, 1*inch, 1.5*inch])
                vitals_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(vitals_table)
                story.append(Spacer(1, 0.2 * inch))
            
            # Laboratory results
            if extraction_data.get('labs'):
                story.append(Paragraph("Laboratory Results", self.styles['SectionHeader']))
                labs_data = [['Test', 'Result', 'Reference', 'Flag']]
                for lab in extraction_data['labs']:
                    labs_data.append([
                        lab.get('test', ''),
                        lab.get('result', ''),
                        lab.get('reference', ''),
                        lab.get('flag', '')
                    ])
                
                labs_table = Table(labs_data, 
                                 colWidths=[2.5*inch, 1*inch, 1.5*inch, 0.5*inch])
                labs_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(labs_table)
                story.append(Spacer(1, 0.2 * inch))
            
            # Diagnoses with ICD codes
            if extraction_data.get('diagnoses'):
                story.append(Paragraph("Diagnoses", self.styles['SectionHeader']))
                for diag in extraction_data['diagnoses']:
                    diag_text = f"• {diag['description']}"
                    if diag.get('icd_code'):
                        diag_text += f" (ICD-10: {diag['icd_code']})"
                    story.append(Paragraph(diag_text, self.styles['MedicationItem']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Raw content fallback
            if extraction_data.get('raw_content') and not any([
                extraction_data.get('vitals'),
                extraction_data.get('labs'),
                extraction_data.get('diagnoses'),
                extraction_data.get('medications'),
                extraction_data.get('procedures')
            ]):
                story.append(Paragraph("Extracted Data", self.styles['SectionHeader']))
                # Split content into paragraphs
                content_lines = extraction_data['raw_content'].split('\n')
                for line in content_lines:
                    if line.strip():
                        story.append(Paragraph(line, self.styles['ContentNormal']))
                story.append(Spacer(1, 0.2 * inch))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated data extraction report PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating data extraction report PDF: {str(e)}")
            return False
    
    def generate_generic_document_pdf(self, title: str, content: str,
                                     output_path: str,
                                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Generate a generic PDF document with basic formatting.
        
        Args:
            title: Document title
            content: Document content (can include basic markdown)
            output_path: Path to save the PDF
            metadata: Optional metadata to include
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            story = []
            
            # Title
            story.append(Paragraph(title, self.styles['CustomTitle']))
            
            # Metadata if provided
            if metadata:
                meta_text = []
                for key, value in metadata.items():
                    if value:
                        meta_text.append(f"{key}: {value}")
                if meta_text:
                    story.append(Paragraph(" | ".join(meta_text), 
                                         self.styles['CustomSubtitle']))
            
            story.append(Spacer(1, 0.3 * inch))
            
            # Process content
            # Split by double newlines for paragraphs
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # Check for headers (lines starting with #)
                    if para.startswith('# '):
                        story.append(Paragraph(para[2:], self.styles['Heading1']))
                    elif para.startswith('## '):
                        story.append(Paragraph(para[3:], self.styles['SectionHeader']))
                    elif para.startswith('### '):
                        story.append(Paragraph(para[4:], self.styles['Heading3']))
                    else:
                        # Regular paragraph
                        story.append(Paragraph(para, self.styles['ContentNormal']))
                    story.append(Spacer(1, 0.1 * inch))
            
            # Build PDF
            doc.build(story, onFirstPage=self._create_header_footer,
                     onLaterPages=self._create_header_footer)
            
            logger.info(f"Generated generic document PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating generic document PDF: {str(e)}")
            return False
    
    def set_header_footer_info(self, header_text: Optional[str] = None,
                              footer_text: Optional[str] = None,
                              logo_path: Optional[str] = None):
        """Set custom header and footer information.

        Args:
            header_text: Text for header
            footer_text: Text for footer
            logo_path: Path to logo image
        """
        if header_text is not None:
            self.header_text = header_text
        if footer_text is not None:
            self.footer_text = footer_text
        if logo_path is not None:
            self.logo_path = logo_path

    def set_simple_letterhead(self, clinic_name: str = "", doctor_name: str = "") -> None:
        """Set simple letterhead information.

        This provides a simple way to add clinic name and doctor name to
        PDF documents without requiring a full logo or complex letterhead.

        Args:
            clinic_name: Name of the clinic for letterhead
            doctor_name: Name of the doctor for letterhead
        """
        self.clinic_name = clinic_name
        self.doctor_name = doctor_name