clear all
set more off
set maxvar 10000
args reference_folder helper_file
do "`helper_file'"
cd "`reference_folder'"
tempname results
postfile `results' str24 scenario str1 freq int time str8 category double q p byte unitq unitp double ch cc using stata_ref_corrected_benchmark_revision.dta, replace
local cats dbbm debm dfgdm dfgkm dfkkm dfksm dfofm dfolm dfotm dfslm dfstm dftim dfum dmnm dmtnm dmttm dmtum dmtvm dmum dojjm dojwm dolm dooem dootm dotm dowbm dowlm dowpm drbm drgdm drgim drsm nfefm nfofm nfolbm nfoldm nfolem nfonm ngarm nlffm nlfim nlglm nlgom nlmfm nlolm nlsm nlxim nmgm nodom nodrm noflm nofum nogfm nogtm nolfm nolnm nolom nolpm nolsm nonm nopcm nopem noppm notm novrm novum nrpm sbom sbopm sboum seovm sfeem sfpm shom shotm shrm shsm shtm sldm slem slgm slim sloom slopm slorm slosm sltpm slwrm slwsm smdm smhnm smhpm smim smom smpm snfcm sobfm sobim soblm sobsm soeem soeum soplm soslm sppm srccm srcpm srdm srepm srevm srkm srobm srogm srolm srovm srsm ssscm sssfm sssrm sssvm ssswm stigm stipm stiwm strlm sturm svim svtm svxm pcfm
quietly {
foreach scenario in benchmark_revision {
foreach freq in M Q {
use `scenario'.dta,clear
if "`freq'"=="Q" {
gen int time_quarter=floor(time_month/3)
collapse (mean) dbbm debm dfgdm dfgkm dfkkm dfksm dfofm dfolm dfotm dfslm dfstm dftim dfum dmnm dmtnm dmttm dmtum dmtvm dmum dojjm dojwm dolm dooem dootm dotm dowbm dowlm dowpm drbm drgdm drgim drsm nfefm nfofm nfolbm nfoldm nfolem nfonm ngarm nlffm nlfim nlglm nlgom nlmfm nlolm nlsm nlxim nmgm nodom nodrm noflm nofum nogfm nogtm nolfm nolnm nolom nolpm nolsm nonm nopcm nopem noppm notm novrm novum nrpm sbom sbopm sboum seovm sfeem sfpm shom shotm shrm shsm shtm sldm slem slgm slim sloom slopm slorm slosm sltpm slwrm slwsm smdm smhnm smhpm smim smom smpm snfcm sobfm sobim soblm sobsm soeem soeum soplm soslm sppm srccm srcpm srdm srepm srevm srkm srobm srogm srolm srovm srsm ssscm sssfm sssrm sssvm ssswm stigm stipm stiwm strlm sturm svim svtm svxm pcfm dbbm_quant debm_quant dfgdm_quant dfgkm_quant dfkkm_quant dfksm_quant dfofm_quant dfolm_quant dfotm_quant dfslm_quant dfstm_quant dftim_quant dfum_quant dmnm_quant dmtnm_quant dmttm_quant dmtum_quant dmtvm_quant dmum_quant dojjm_quant dojwm_quant dolm_quant dooem_quant dootm_quant dotm_quant dowbm_quant dowlm_quant dowpm_quant drbm_quant drgdm_quant drgim_quant drsm_quant nfefm_quant nfofm_quant nfolbm_quant nfoldm_quant nfolem_quant nfonm_quant ngarm_quant nlffm_quant nlfim_quant nlglm_quant nlgom_quant nlmfm_quant nlolm_quant nlsm_quant nlxim_quant nmgm_quant nodom_quant nodrm_quant noflm_quant nofum_quant nogfm_quant nogtm_quant nolfm_quant nolnm_quant nolom_quant nolpm_quant nolsm_quant nonm_quant nopcm_quant nopem_quant noppm_quant notm_quant novrm_quant novum_quant nrpm_quant sbom_quant sbopm_quant sboum_quant seovm_quant sfeem_quant sfpm_quant shom_quant shotm_quant shrm_quant shsm_quant shtm_quant sldm_quant slem_quant slgm_quant slim_quant sloom_quant slopm_quant slorm_quant slosm_quant sltpm_quant slwrm_quant slwsm_quant smdm_quant smhnm_quant smhpm_quant smim_quant smom_quant smpm_quant snfcm_quant sobfm_quant sobim_quant soblm_quant sobsm_quant soeem_quant soeum_quant soplm_quant soslm_quant sppm_quant srccm_quant srcpm_quant srdm_quant srepm_quant srevm_quant srkm_quant srobm_quant srogm_quant srolm_quant srovm_quant srsm_quant ssscm_quant sssfm_quant sssrm_quant sssvm_quant ssswm_quant stigm_quant stipm_quant stiwm_quant strlm_quant sturm_quant svim_quant svtm_quant svxm_quant pcfm_quant dbbm_spend debm_spend dfgdm_spend dfgkm_spend dfkkm_spend dfksm_spend dfofm_spend dfolm_spend dfotm_spend dfslm_spend dfstm_spend dftim_spend dfum_spend dmnm_spend dmtnm_spend dmttm_spend dmtum_spend dmtvm_spend dmum_spend dojjm_spend dojwm_spend dolm_spend dooem_spend dootm_spend dotm_spend dowbm_spend dowlm_spend dowpm_spend drbm_spend drgdm_spend drgim_spend drsm_spend nfefm_spend nfofm_spend nfolbm_spend nfoldm_spend nfolem_spend nfonm_spend ngarm_spend nlffm_spend nlfim_spend nlglm_spend nlgom_spend nlmfm_spend nlolm_spend nlsm_spend nlxim_spend nmgm_spend nodom_spend nodrm_spend noflm_spend nofum_spend nogfm_spend nogtm_spend nolfm_spend nolnm_spend nolom_spend nolpm_spend nolsm_spend nonm_spend nopcm_spend nopem_spend noppm_spend notm_spend novrm_spend novum_spend nrpm_spend sbom_spend sbopm_spend sboum_spend seovm_spend sfeem_spend sfpm_spend shom_spend shotm_spend shrm_spend shsm_spend shtm_spend sldm_spend slem_spend slgm_spend slim_spend sloom_spend slopm_spend slorm_spend slosm_spend sltpm_spend slwrm_spend slwsm_spend smdm_spend smhnm_spend smhpm_spend smim_spend smom_spend smpm_spend snfcm_spend sobfm_spend sobim_spend soblm_spend sobsm_spend soeem_spend soeum_spend soplm_spend soslm_spend sppm_spend srccm_spend srcpm_spend srdm_spend srepm_spend srevm_spend srkm_spend srobm_spend srogm_spend srolm_spend srovm_spend srsm_spend ssscm_spend sssfm_spend sssrm_spend sssvm_spend ssswm_spend stigm_spend stipm_spend stiwm_spend strlm_spend sturm_spend svim_spend svtm_spend svxm_spend pcfm_spend pce_spend core_spend,by(time_quarter)
rename time_quarter time_month
}
tsset time_month
foreach c of local cats {
gen float delta_`c'=(`c'-L.`c')/L.`c'
gen float logp_`c'=ln(`c')
replace `c'_quant=ln(`c'_quant)
local zero=0
}
local lag=cond("`freq'"=="M",12,4)
local win=cond("`freq'"=="M",120,40)
local dates "130 131 132 133 134 135 136 137 138 139 140 141 801"
if "`freq'"=="Q" local dates "44 45 46 47 267"
foreach t of local dates {
foreach c of local cats {
foreach eq in q p {
local dep=cond("`eq'"=="q","`c'_quant","logp_`c'")
regress `dep' L(1/`lag').`c'_quant L(1/`lag').logp_`c' if inrange(time_month,`t'-`win',`t')
predict float error,residuals
sd_zero_exact_fit error, regressors("L(1/`lag').`c'_quant L(1/`lag').logp_`c'")
local sd_wasunit=r(unit_last)
gen byte unit=0
replace unit=`sd_wasunit' if time_month==`t'
sum error if inrange(time_month,`t'-`win',`t')
gen float z=error/r(sd)
sum z if time_month==`t'
local score`eq'=r(mean)
sum unit if time_month==`t'
local unit`eq'=r(mean)
drop error z unit
}
gen float ch=(L.`c'_spend/L.pce_spend)*delta_`c'
gen float cc=(L.`c'_spend/L.core_spend)*delta_`c'
sum ch if time_month==`t'
local ch=r(mean)
sum cc if time_month==`t'
local cc=r(mean)
post `results' ("`scenario'") ("`freq'") (`t') ("`c'") (`scoreq') (`scorep') (`unitq') (`unitp') (`ch') (`cc')
drop ch cc
}
}
}
}
}
postclose `results'
exit,clear
