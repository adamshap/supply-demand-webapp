from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
FIX=Path(__file__).parent/'fixtures'
sys.path.insert(0,str(ROOT/'automation'))
from engine import calculate
from exports import FILES, build, stata_round
from workbook import read_frames,write_frames
from update import candidates,merge_frame,rebuild_required,run,file_hash,PUBLIC_FILES

class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel=pd.read_csv(FIX/'bea_2026_10.csv.gz',index_col='time_month')
        cls.categories=list(pd.read_csv(ROOT/'automation/categories.csv').haver_code)
        cls.schema=json.loads((ROOT/'automation/schema.json').read_text())
        cls.csvs,cls.excels=candidates(cls.panel,cls.categories,cls.schema,True)

    def test_all_six_csvs_against_full_stata_release(self):
        for file,frame in self.csvs.items():
            expected=pd.read_csv(FIX/(file+'.gz'))
            self.assertEqual(list(frame.date),list(expected.date))
            self.assertEqual(list(frame.columns),list(expected.columns))
            np.testing.assert_allclose(frame.drop(columns='date'),expected.drop(columns='date'),atol=1e-6,rtol=0,equal_nan=True,err_msg=file)

    def test_excel_all_six_sheets_and_roundtrip(self):
        expected=read_frames(FIX/'supply_demand_public.xlsx',self.schema)
        for file,frame in self.excels.items():
            self.assertEqual(list(frame.date),list(expected[file].date))
            np.testing.assert_allclose(frame.drop(columns='date'),expected[file].drop(columns='date'),atol=1e-6,rtol=0,equal_nan=True,err_msg=file)
        with tempfile.TemporaryDirectory() as folder:
            write_frames(self.excels,FIX/'supply_demand_public.xlsx',Path(folder)/'test.xlsx')

    def test_incremental_windows_and_missing_annual_merge(self):
        csvs,_=candidates(self.panel,self.categories,self.schema,False)
        for file,frame in csvs.items():
            count=18 if 'goods_services' in file else 25
            self.assertEqual(len(frame),count)
            old=pd.read_csv(FIX/(file+'.gz'))
            merged=merge_frame(old,frame,False,'quarterly' in file)
            # Missing annual values at the start of the new window keep the baseline.
            first=frame.iloc[0]; year=[c for c in frame if c.endswith('_yoy')][0]
            self.assertTrue(pd.isna(first[year]))
            row=merged[merged.date==first.date].iloc[0]
            self.assertEqual(row[year],old[old.date==first.date].iloc[0][year])
            np.testing.assert_allclose(merged.drop(columns='date'),old.drop(columns='date'),atol=1e-6,rtol=0,equal_nan=True)
            with self.assertRaises(ValueError):merge_frame(old,frame,True,'quarterly' in file)

    def test_september_and_missed_release_benchmark(self):
        self.assertTrue(rebuild_required('2026-08','2026-09'))
        self.assertTrue(rebuild_required('2026-08','2026-10'))
        self.assertFalse(rebuild_required('2026-09','2026-10'))
        self.assertTrue(rebuild_required('2026-10','2026-10',True))
        with self.assertRaises(ValueError):rebuild_required('2026-10','2026-09')

    def test_quarterly_workbook_units_and_stata_rounding(self):
        file='supply_demand_quarterly.csv'
        for c in self.csvs[file]:
            if c.endswith('_qoq'):
                np.testing.assert_allclose(self.csvs[file][c],self.excels[file][c]*100,atol=1e-6,rtol=0)
        # Stata ties round toward positive infinity, using binary arithmetic.
        np.testing.assert_allclose(stata_round(np.array([.005,-.005,.145,-.195]),.01),[.01,0,.14,-.19],atol=1e-15)
        self.assertEqual(file_hash('x.csv',b'a,b\r\n1,2\r\n'),file_hash('x.csv',b'a,b\n1,2\n'))

    def test_changed_historical_tie_inputs_fail_closed(self):
        changed=self.panel.copy();changed.loc[130,'drgim']+=.001
        with self.assertRaisesRegex(ValueError,'Historical numerical-tie inputs changed'):
            calculate(changed,self.categories,[130])

    def test_update_installs_seven_exports_and_date_only_after_validation(self):
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'automation').mkdir()
            for name in ['categories.csv','schema.json']:
                shutil.copyfile(ROOT/'automation'/name,root/'automation'/name)
            (root/'automation/state.json').write_text('{}')
            old_excel={}
            for file,frame in self.csvs.items():
                frame.iloc[:-1].to_csv(root/file,index=False)
                old_excel[file]=self.excels[file].iloc[:-1]
            write_frames(old_excel,FIX/'supply_demand_public.xlsx',root/'supply_demand_public.xlsx')
            before={n:(root/n).read_bytes() for n in PUBLIC_FILES}
            with patch('update.BeaClient'),patch('update.inputs',return_value=self.panel),patch('update.candidates',return_value=(self.csvs,self.excels)):
                with patch('update.release_metadata',side_effect=RuntimeError('metadata unavailable')):
                    with self.assertRaises(RuntimeError):run(root,'update',False,None,root/'out','2026-10','2026-11-25T13:30:00+00:00')
                self.assertEqual(before,{n:(root/n).read_bytes() for n in PUBLIC_FILES})
                report=run(root,'update',False,None,root/'out','2026-10','2026-11-25T13:30:00+00:00')
            self.assertTrue(report['data_changed'])
            meta=json.loads((root/'data-update.json').read_text())
            self.assertEqual(meta['data_through'],'2026-10');self.assertEqual(meta['bea_release_date'],'2026-11-25')
            state=json.loads((root/'automation/state.json').read_text())
            self.assertEqual(state['published_files_sha256'],{n:file_hash(n,(root/n).read_bytes()) for n in PUBLIC_FILES})
            for file,expected in self.csvs.items():
                actual=pd.read_csv(root/file)
                self.assertEqual(list(actual.date),list(expected.date))
                np.testing.assert_allclose(actual.drop(columns='date'),expected.drop(columns='date'),atol=1e-6,rtol=0,equal_nan=True)

    def test_already_uploaded_month_gets_current_release_metadata(self):
        import shutil,gzip
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'automation').mkdir()
            for name in ['categories.csv','schema.json']:shutil.copyfile(ROOT/'automation'/name,root/'automation'/name)
            (root/'automation/state.json').write_text('{}')
            for name in FILES:(root/name).write_bytes(gzip.decompress((FIX/(name+'.gz')).read_bytes()))
            shutil.copyfile(FIX/'supply_demand_public.xlsx',root/'supply_demand_public.xlsx')
            (root/'data-update.json').write_text(json.dumps({'data_through':'2026-09','bea_release_date':'2026-10-29'}))
            with patch('update.BeaClient'),patch('update.inputs',return_value=self.panel),patch('update.candidates',return_value=(self.csvs,self.excels)):
                report=run(root,'update',False,None,root/'out','2026-10','2026-11-25T13:30:00+00:00')
            self.assertTrue(report['data_changed'])
            metadata=json.loads((root/'data-update.json').read_text())
            self.assertEqual(metadata['data_through'],'2026-10')
            self.assertEqual(metadata['bea_release_date'],'2026-11-25')

    def test_waiting_release_and_network_failure_preserve_files(self):
        paths=[ROOT/name for name in PUBLIC_FILES]+[ROOT/'automation/state.json',ROOT/'data-update.json']
        before=[p.read_bytes() for p in paths]
        with tempfile.TemporaryDirectory() as folder:
            with patch('update.BeaClient'),patch('update.inputs',return_value=self.panel),patch('update.candidates',side_effect=AssertionError('must not calculate')):
                report=run(ROOT,'update',False,None,Path(folder),'2026-11')
            self.assertEqual(report['status'],'waiting_for_release')
            self.assertFalse(report['changed'])
            with patch('update.BeaClient',side_effect=RuntimeError('simulated network failure')):
                with self.assertRaises(RuntimeError):run(ROOT,'update',False,None,Path(folder))
        self.assertEqual(before,[p.read_bytes() for p in paths])

if __name__=='__main__':unittest.main()
