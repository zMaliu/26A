$xelatex = 'xelatex -interaction=nonstopmode -file-line-error -synctex=1 %O %S';
$pdflatex = $xelatex;
$pdf_mode = 5;
$out_dir = 'output/pdf';
$aux_dir = 'output/pdf';
$bibtex = 'bibtex %O %B';
$ENV{'TEXINPUTS'} = 'E:/software/latex//;' . ($ENV{'TEXINPUTS'} // '');
